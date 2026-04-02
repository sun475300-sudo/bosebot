"""Tests for FAQ diff/snapshot system (src/faq_diff.py) and API endpoints."""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.faq_manager import FAQManager
from src.faq_diff import FAQDiffEngine


# --- Sample data ---

SAMPLE_FAQ_DATA = {
    "faq_version": "3.0.0",
    "last_updated": "2026-03-27",
    "items": [
        {
            "id": "A",
            "category": "GENERAL",
            "question": "What is a bonded exhibition?",
            "answer": "A bonded exhibition area for foreign goods.",
            "legal_basis": ["Act 190"],
            "notes": "",
            "keywords": ["bonded", "exhibition"],
        },
        {
            "id": "B",
            "category": "IMPORT_EXPORT",
            "question": "Is declaration needed for import?",
            "answer": "Yes, you must declare to customs.",
            "legal_basis": ["Notification 10"],
            "notes": "",
            "keywords": ["import", "declaration"],
        },
    ],
}


@pytest.fixture
def env(tmp_path):
    """Create isolated FAQ manager and diff engine."""
    faq_file = tmp_path / "faq.json"
    faq_file.write_text(json.dumps(SAMPLE_FAQ_DATA, ensure_ascii=False), encoding="utf-8")
    history_db = str(tmp_path / "faq_history.db")
    snapshot_db = str(tmp_path / "faq_snapshots.db")
    manager = FAQManager(faq_path=str(faq_file), history_db_path=history_db)
    engine = FAQDiffEngine(manager, snapshot_db_path=snapshot_db)
    return manager, engine


# --- Snapshot creation and listing ---

class TestSnapshotCreation:
    def test_snapshot_returns_metadata(self, env):
        manager, engine = env
        result = engine.snapshot(label="v1")
        assert result["id"] == 1
        assert result["label"] == "v1"
        assert result["item_count"] == 2
        assert "timestamp" in result

    def test_snapshot_without_label(self, env):
        manager, engine = env
        result = engine.snapshot()
        assert result["label"] is None
        assert result["item_count"] == 2

    def test_list_snapshots(self, env):
        manager, engine = env
        engine.snapshot(label="first")
        engine.snapshot(label="second")
        snapshots = engine.list_snapshots()
        assert len(snapshots) == 2
        assert snapshots[0]["label"] == "first"
        assert snapshots[1]["label"] == "second"
        assert snapshots[0]["item_count"] == 2

    def test_list_snapshots_empty(self, env):
        _, engine = env
        assert engine.list_snapshots() == []


# --- Diff with added/removed/modified ---

class TestDiff:
    def test_identical_snapshots(self, env):
        manager, engine = env
        s1 = engine.snapshot(label="s1")
        s2 = engine.snapshot(label="s2")
        result = engine.diff(s1["id"], s2["id"])
        assert result["added"] == []
        assert result["removed"] == []
        assert result["modified"] == []
        assert len(result["unchanged"]) == 2

    def test_added_items(self, env):
        manager, engine = env
        s1 = engine.snapshot(label="before")
        manager.create({
            "id": "C",
            "category": "GENERAL",
            "question": "New question?",
            "answer": "New answer.",
        })
        s2 = engine.snapshot(label="after")
        result = engine.diff(s1["id"], s2["id"])
        assert len(result["added"]) == 1
        assert result["added"][0]["id"] == "C"
        assert result["removed"] == []

    def test_removed_items(self, env):
        manager, engine = env
        s1 = engine.snapshot(label="before")
        manager.delete("B")
        s2 = engine.snapshot(label="after")
        result = engine.diff(s1["id"], s2["id"])
        assert len(result["removed"]) == 1
        assert result["removed"][0]["id"] == "B"
        assert result["added"] == []

    def test_modified_items(self, env):
        manager, engine = env
        s1 = engine.snapshot(label="before")
        manager.update("A", {
            "category": "GENERAL",
            "question": "Updated question?",
            "answer": "A bonded exhibition area for foreign goods.",
        })
        s2 = engine.snapshot(label="after")
        result = engine.diff(s1["id"], s2["id"])
        assert len(result["modified"]) == 1
        mod = result["modified"][0]
        assert mod["id"] == "A"
        assert "question" in mod["fields"]
        assert mod["fields"]["question"]["old"] == "What is a bonded exhibition?"
        assert mod["fields"]["question"]["new"] == "Updated question?"

    def test_mixed_changes(self, env):
        manager, engine = env
        s1 = engine.snapshot(label="before")
        manager.create({
            "id": "C",
            "category": "GENERAL",
            "question": "New?",
            "answer": "Yes.",
        })
        manager.delete("B")
        manager.update("A", {
            "category": "GENERAL",
            "question": "What is a bonded exhibition?",
            "answer": "Updated answer.",
        })
        s2 = engine.snapshot(label="after")
        result = engine.diff(s1["id"], s2["id"])
        assert len(result["added"]) == 1
        assert len(result["removed"]) == 1
        assert len(result["modified"]) == 1

    def test_diff_invalid_snapshot_id(self, env):
        _, engine = env
        engine.snapshot()
        with pytest.raises(KeyError):
            engine.diff(1, 999)


# --- diff_current ---

class TestDiffCurrent:
    def test_diff_current_no_changes(self, env):
        manager, engine = env
        s1 = engine.snapshot(label="baseline")
        result = engine.diff_current(s1["id"])
        assert result["added"] == []
        assert result["removed"] == []
        assert result["modified"] == []
        assert len(result["unchanged"]) == 2

    def test_diff_current_with_changes(self, env):
        manager, engine = env
        s1 = engine.snapshot(label="baseline")
        manager.create({
            "id": "C",
            "category": "GENERAL",
            "question": "Extra?",
            "answer": "Extra.",
        })
        result = engine.diff_current(s1["id"])
        assert len(result["added"]) == 1
        assert result["added"][0]["id"] == "C"


# --- Rollback ---

class TestRollback:
    def test_rollback_restores_items(self, env):
        manager, engine = env
        s1 = engine.snapshot(label="baseline")
        # Make changes
        manager.create({
            "id": "C",
            "category": "GENERAL",
            "question": "Extra?",
            "answer": "Extra.",
        })
        manager.delete("A")
        assert len(manager.list_all()) == 2  # B, C

        count = engine.rollback_to(s1["id"])
        assert count == 2
        items = manager.list_all()
        ids = {item["id"] for item in items}
        assert ids == {"A", "B"}

    def test_rollback_invalid_snapshot(self, env):
        _, engine = env
        with pytest.raises(KeyError):
            engine.rollback_to(999)


# --- Change summary ---

class TestChangeSummary:
    def test_summary_with_changes(self, env):
        manager, engine = env
        s1 = engine.snapshot()
        manager.create({
            "id": "C",
            "category": "GENERAL",
            "question": "New?",
            "answer": "Yes.",
        })
        manager.delete("B")
        manager.update("A", {
            "category": "GENERAL",
            "question": "Updated?",
            "answer": "Updated.",
        })
        s2 = engine.snapshot()
        diff_result = engine.diff(s1["id"], s2["id"])
        summary = engine.get_change_summary(diff_result)
        assert "Added 1 item(s): C" in summary
        assert "Removed 1 item(s): B" in summary
        assert "Modified item A" in summary

    def test_summary_no_changes(self, env):
        _, engine = env
        s1 = engine.snapshot()
        s2 = engine.snapshot()
        diff_result = engine.diff(s1["id"], s2["id"])
        summary = engine.get_change_summary(diff_result)
        assert "2 item(s) unchanged" in summary

    def test_summary_empty_diff(self, env):
        """Diff with no items at all."""
        _, engine = env
        diff_result = {
            "added": [],
            "removed": [],
            "modified": [],
            "unchanged": [],
        }
        summary = engine.get_change_summary(diff_result)
        assert summary == "No differences found."


# --- API endpoint tests ---

class TestFAQDiffAPI:
    @pytest.fixture
    def client(self):
        from web_server import app
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_create_snapshot(self, client):
        resp = client.post(
            "/api/admin/faq/snapshot",
            json={"label": "test-snap"},
            content_type="application/json",
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["label"] == "test-snap"
        assert "id" in data
        assert "item_count" in data

    def test_list_snapshots(self, client):
        client.post("/api/admin/faq/snapshot", json={"label": "snap1"})
        resp = client.get("/api/admin/faq/snapshots")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "snapshots" in data
        assert isinstance(data["snapshots"], list)

    def test_diff_endpoint(self, client):
        r1 = client.post("/api/admin/faq/snapshot", json={"label": "a"})
        id_a = r1.get_json()["id"]
        r2 = client.post("/api/admin/faq/snapshot", json={"label": "b"})
        id_b = r2.get_json()["id"]
        resp = client.get(f"/api/admin/faq/diff?a={id_a}&b={id_b}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "diff" in data
        assert "summary" in data

    def test_diff_missing_params(self, client):
        resp = client.get("/api/admin/faq/diff")
        assert resp.status_code == 400

    def test_rollback_endpoint(self, client):
        r1 = client.post("/api/admin/faq/snapshot", json={"label": "pre-rollback"})
        snap_id = r1.get_json()["id"]
        resp = client.post(
            "/api/admin/faq/rollback",
            json={"snapshot_id": snap_id},
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "restored_items" in data

    def test_rollback_missing_id(self, client):
        resp = client.post(
            "/api/admin/faq/rollback",
            json={},
            content_type="application/json",
        )
        assert resp.status_code == 400
