"""FAQ version comparison and diff system.

Provides FAQDiffEngine for creating snapshots of FAQ state, comparing
snapshots, and rolling back to previous versions.
"""

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class FAQDiffEngine:
    """Manages FAQ snapshots, diffs, and rollbacks using SQLite storage."""

    def __init__(self, faq_manager, snapshot_db_path=None):
        self.faq_manager = faq_manager
        self.snapshot_db_path = snapshot_db_path or os.path.join(
            BASE_DIR, "data", "faq_snapshots.db"
        )
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """Create snapshot tables if they do not exist."""
        os.makedirs(os.path.dirname(self.snapshot_db_path), exist_ok=True)
        conn = sqlite3.connect(self.snapshot_db_path)
        try:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    label TEXT,
                    item_count INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    data TEXT NOT NULL
                )"""
            )
            conn.commit()
        finally:
            conn.close()

    def snapshot(self, label=None):
        """Save current FAQ state as a snapshot. Returns snapshot metadata."""
        with self._lock:
            items = self.faq_manager.list_all()
            # Strip enriched fields that are not part of the core data
            clean_items = []
            for item in items:
                clean = {k: v for k, v in item.items()
                         if k not in ("keywords_count", "last_modified")}
                clean_items.append(clean)

            timestamp = datetime.now(timezone.utc).isoformat()
            data_json = json.dumps(clean_items, ensure_ascii=False)

            conn = sqlite3.connect(self.snapshot_db_path)
            try:
                cursor = conn.execute(
                    "INSERT INTO snapshots (label, item_count, timestamp, data) "
                    "VALUES (?, ?, ?, ?)",
                    (label, len(clean_items), timestamp, data_json),
                )
                conn.commit()
                snapshot_id = cursor.lastrowid
            finally:
                conn.close()

            return {
                "id": snapshot_id,
                "label": label,
                "item_count": len(clean_items),
                "timestamp": timestamp,
            }

    def list_snapshots(self):
        """Return all snapshots with metadata (without full data)."""
        conn = sqlite3.connect(self.snapshot_db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT id, label, item_count, timestamp FROM snapshots "
                "ORDER BY id ASC"
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def _get_snapshot_items(self, snapshot_id):
        """Load items from a snapshot by ID. Raises KeyError if not found."""
        conn = sqlite3.connect(self.snapshot_db_path)
        try:
            row = conn.execute(
                "SELECT data FROM snapshots WHERE id = ?", (snapshot_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"Snapshot ID {snapshot_id} not found")
            return json.loads(row[0])
        finally:
            conn.close()

    def diff(self, snapshot_id_a, snapshot_id_b):
        """Compare two snapshots. Returns dict with added/removed/modified/unchanged."""
        items_a = self._get_snapshot_items(snapshot_id_a)
        items_b = self._get_snapshot_items(snapshot_id_b)
        return self._compute_diff(items_a, items_b)

    def diff_current(self, snapshot_id):
        """Diff current FAQ state against a snapshot."""
        snapshot_items = self._get_snapshot_items(snapshot_id)

        current_items = self.faq_manager.list_all()
        clean_current = []
        for item in current_items:
            clean = {k: v for k, v in item.items()
                     if k not in ("keywords_count", "last_modified")}
            clean_current.append(clean)

        return self._compute_diff(snapshot_items, clean_current)

    def _compute_diff(self, items_a, items_b):
        """Compute diff between two item lists.

        Returns dict with keys: added, removed, modified, unchanged.
        Items are matched by their 'id' field.
        """
        map_a = {item["id"]: item for item in items_a}
        map_b = {item["id"]: item for item in items_b}

        ids_a = set(map_a.keys())
        ids_b = set(map_b.keys())

        added = [map_b[faq_id] for faq_id in sorted(ids_b - ids_a)]
        removed = [map_a[faq_id] for faq_id in sorted(ids_a - ids_b)]

        modified = []
        unchanged = []

        for faq_id in sorted(ids_a & ids_b):
            item_a = map_a[faq_id]
            item_b = map_b[faq_id]
            if item_a == item_b:
                unchanged.append(item_a)
            else:
                field_diffs = {}
                all_keys = set(item_a.keys()) | set(item_b.keys())
                for key in sorted(all_keys):
                    val_a = item_a.get(key)
                    val_b = item_b.get(key)
                    if val_a != val_b:
                        field_diffs[key] = {"old": val_a, "new": val_b}
                modified.append({
                    "id": faq_id,
                    "fields": field_diffs,
                    "old": item_a,
                    "new": item_b,
                })

        return {
            "added": added,
            "removed": removed,
            "modified": modified,
            "unchanged": unchanged,
        }

    def rollback_to(self, snapshot_id):
        """Restore FAQ data from a snapshot.

        Deletes all current items and recreates them from the snapshot.
        Returns the count of restored items.
        """
        snapshot_items = self._get_snapshot_items(snapshot_id)

        # Delete all current items
        current_items = self.faq_manager.list_all()
        for item in current_items:
            try:
                self.faq_manager.delete(item["id"])
            except KeyError:
                pass

        # Recreate items from snapshot
        for item in snapshot_items:
            self.faq_manager.create(item)

        return len(snapshot_items)

    def get_change_summary(self, diff_result):
        """Return a human-readable summary string from a diff result."""
        parts = []
        added_count = len(diff_result["added"])
        removed_count = len(diff_result["removed"])
        modified_count = len(diff_result["modified"])
        unchanged_count = len(diff_result["unchanged"])

        if added_count:
            ids = ", ".join(item["id"] for item in diff_result["added"])
            parts.append(f"Added {added_count} item(s): {ids}")
        if removed_count:
            ids = ", ".join(item["id"] for item in diff_result["removed"])
            parts.append(f"Removed {removed_count} item(s): {ids}")
        if modified_count:
            for mod in diff_result["modified"]:
                fields = ", ".join(mod["fields"].keys())
                parts.append(f"Modified item {mod['id']}: changed {fields}")
        if unchanged_count:
            parts.append(f"{unchanged_count} item(s) unchanged")

        if not parts:
            return "No differences found."

        return "\n".join(parts)
