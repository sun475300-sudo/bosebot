"""Conversation flow analysis and visualization data generator.

Analyzes conversation flows within sessions, computes transition matrices,
identifies drop-off points, and generates Sankey diagram data.
"""

import os
import sqlite3
import threading
from collections import Counter
from datetime import datetime


class FlowAnalyzer:
    """Analyzes conversation session flows for visualization and reporting."""

    def __init__(self, db_path=None):
        if db_path is None:
            db_path = os.path.join("logs", "flow_analysis.db")
        self.db_path = db_path
        self._local = threading.local()
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._init_table()

    def _get_conn(self):
        """Return a thread-local SQLite connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_table(self):
        """Create the session_flows table if it does not exist."""
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS session_flows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                turn_index INTEGER NOT NULL,
                category TEXT NOT NULL,
                query TEXT,
                response_type TEXT DEFAULT 'unknown',
                satisfaction_score REAL DEFAULT 0.0,
                timestamp TEXT NOT NULL
            )
        """)
        conn.commit()

    def record_turn(self, session_id: str, category: str, query: str = None,
                    response_type: str = "unknown", satisfaction_score: float = 0.0):
        """Record a single conversation turn in a session flow."""
        conn = self._get_conn()
        # Determine next turn index for this session
        row = conn.execute(
            "SELECT COALESCE(MAX(turn_index), -1) + 1 AS next_idx "
            "FROM session_flows WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        turn_index = row["next_idx"]
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO session_flows "
            "(session_id, turn_index, category, query, response_type, satisfaction_score, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (session_id, turn_index, category, query, response_type, satisfaction_score, timestamp),
        )
        conn.commit()

    def analyze_session(self, session_id: str) -> list[str]:
        """Return the conversation flow path (category sequence) for a session."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT category FROM session_flows "
            "WHERE session_id = ? ORDER BY turn_index",
            (session_id,),
        ).fetchall()
        return [row["category"] for row in rows]

    def get_flow_paths(self, limit: int = 100) -> list[dict]:
        """Return all recent conversation paths.

        Returns a list of dicts with session_id and path (category list).
        """
        conn = self._get_conn()
        session_ids = conn.execute(
            "SELECT session_id, MAX(id) AS max_id FROM session_flows "
            "GROUP BY session_id ORDER BY max_id DESC LIMIT ?",
            (limit,),
        ).fetchall()

        result = []
        for sid_row in session_ids:
            sid = sid_row["session_id"]
            path = self.analyze_session(sid)
            result.append({"session_id": sid, "path": path})
        return result

    def get_transition_matrix(self) -> dict[str, dict[str, int]]:
        """Return category-to-category transition counts.

        Returns a nested dict: {from_category: {to_category: count}}.
        """
        conn = self._get_conn()
        # Get all sessions and their ordered categories
        session_ids = conn.execute(
            "SELECT DISTINCT session_id FROM session_flows"
        ).fetchall()

        matrix: dict[str, dict[str, int]] = {}

        for sid_row in session_ids:
            sid = sid_row["session_id"]
            rows = conn.execute(
                "SELECT category FROM session_flows "
                "WHERE session_id = ? ORDER BY turn_index",
                (sid,),
            ).fetchall()
            categories = [r["category"] for r in rows]
            for i in range(len(categories) - 1):
                src = categories[i]
                dst = categories[i + 1]
                if src not in matrix:
                    matrix[src] = {}
                matrix[src][dst] = matrix[src].get(dst, 0) + 1

        return matrix

    def get_drop_off_points(self) -> dict[str, int]:
        """Identify where users stop asking (last category in each session).

        Returns a dict: {category: count_of_sessions_ending_here}.
        """
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT sf.category FROM session_flows sf "
            "INNER JOIN ("
            "  SELECT session_id, MAX(turn_index) AS max_turn "
            "  FROM session_flows GROUP BY session_id"
            ") last ON sf.session_id = last.session_id AND sf.turn_index = last.max_turn"
        ).fetchall()

        counts: dict[str, int] = {}
        for row in rows:
            cat = row["category"]
            counts[cat] = counts.get(cat, 0) + 1
        return counts

    def get_common_paths(self, top_n: int = 10) -> list[dict]:
        """Return the most frequent conversation paths.

        Returns list of dicts with 'path' (tuple of categories) and 'count'.
        """
        conn = self._get_conn()
        session_ids = conn.execute(
            "SELECT DISTINCT session_id FROM session_flows"
        ).fetchall()

        path_counter: Counter = Counter()
        for sid_row in session_ids:
            sid = sid_row["session_id"]
            path = tuple(self.analyze_session(sid))
            if path:
                path_counter[path] += 1

        return [
            {"path": list(path), "count": count}
            for path, count in path_counter.most_common(top_n)
        ]

    def get_avg_turns_per_category(self) -> dict[str, float]:
        """Return average conversation length per starting category."""
        conn = self._get_conn()
        # Get first category and session length for each session
        rows = conn.execute(
            "SELECT sf.session_id, sf.category AS start_category, counts.total_turns "
            "FROM session_flows sf "
            "INNER JOIN ("
            "  SELECT session_id, COUNT(*) AS total_turns FROM session_flows GROUP BY session_id"
            ") counts ON sf.session_id = counts.session_id "
            "WHERE sf.turn_index = 0"
        ).fetchall()

        category_turns: dict[str, list[int]] = {}
        for row in rows:
            cat = row["start_category"]
            if cat not in category_turns:
                category_turns[cat] = []
            category_turns[cat].append(row["total_turns"])

        return {
            cat: round(sum(turns) / len(turns), 2)
            for cat, turns in category_turns.items()
            if turns
        }

    def get_satisfaction_by_path(self) -> list[dict]:
        """Return satisfaction score grouped by conversation path.

        Returns list of dicts with 'path' and 'avg_satisfaction'.
        """
        conn = self._get_conn()
        session_ids = conn.execute(
            "SELECT DISTINCT session_id FROM session_flows"
        ).fetchall()

        path_scores: dict[tuple, list[float]] = {}
        for sid_row in session_ids:
            sid = sid_row["session_id"]
            rows = conn.execute(
                "SELECT category, satisfaction_score FROM session_flows "
                "WHERE session_id = ? ORDER BY turn_index",
                (sid,),
            ).fetchall()
            if not rows:
                continue
            path = tuple(r["category"] for r in rows)
            avg_score = sum(r["satisfaction_score"] for r in rows) / len(rows)
            if path not in path_scores:
                path_scores[path] = []
            path_scores[path].append(avg_score)

        result = []
        for path, scores in path_scores.items():
            result.append({
                "path": list(path),
                "avg_satisfaction": round(sum(scores) / len(scores), 4),
                "session_count": len(scores),
            })
        result.sort(key=lambda x: x["avg_satisfaction"], reverse=True)
        return result

    def generate_sankey_data(self) -> dict:
        """Generate formatted data for a Sankey diagram.

        Returns dict with 'nodes' (list of {id, name}) and
        'links' (list of {source, target, value}).
        """
        matrix = self.get_transition_matrix()

        # Collect all unique categories
        categories = set()
        for src, targets in matrix.items():
            categories.add(src)
            for dst in targets:
                categories.add(dst)

        # Build nodes: each category at each step gets a unique node
        # For simplicity, use category names as node IDs
        node_list = sorted(categories)
        node_index = {name: idx for idx, name in enumerate(node_list)}

        nodes = [{"id": idx, "name": name} for name, idx in node_index.items()]
        links = []
        for src, targets in matrix.items():
            for dst, count in targets.items():
                links.append({
                    "source": node_index[src],
                    "target": node_index[dst],
                    "value": count,
                })

        return {"nodes": nodes, "links": links}

    def generate_flow_report(self) -> dict:
        """Generate a comprehensive flow analysis report."""
        return {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "common_paths": self.get_common_paths(top_n=10),
            "drop_off_points": self.get_drop_off_points(),
            "transition_matrix": self.get_transition_matrix(),
            "avg_turns_per_category": self.get_avg_turns_per_category(),
            "satisfaction_by_path": self.get_satisfaction_by_path(),
            "sankey_data": self.generate_sankey_data(),
        }

    def close(self):
        """Close the DB connection."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
