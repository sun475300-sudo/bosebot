"""Tests for ConversationManagerV3 and TopicTracker."""

from __future__ import annotations

import os
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.conversation_manager_v3 import (  # noqa: E402
    ConversationManagerV3,
    TopicTracker,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def manager(tmp_path):
    db_path = str(tmp_path / "conv_v3.db")
    return ConversationManagerV3(db_path=db_path)


@pytest.fixture
def tracker():
    return TopicTracker()


@pytest.fixture
def client():
    # Ensure module-level Flask app is importable lazily to avoid side-effects
    # when the suite runs without a network.
    from web_server import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Turn recording
# ---------------------------------------------------------------------------


class TestTurnRecording:
    def test_add_turn_returns_positive_id(self, manager):
        row_id = manager.add_turn(
            "s1", "보세전시장이 무엇인가요?", "외국물품을 전시...", "GENERAL", []
        )
        assert isinstance(row_id, int)
        assert row_id > 0

    def test_add_turn_auto_classifies_when_category_missing(self, manager):
        manager.add_turn("s1", "특허 신청은 어떻게 하나요?", "세관에 신청서를 제출...")
        ctx = manager.get_context("s1")
        assert len(ctx) == 1
        assert ctx[0]["category"]  # auto-assigned from classifier

    def test_add_turn_persists_entities(self, manager):
        manager.add_turn(
            "s1",
            "견본품 관세는?",
            "일정 금액 이하 면제",
            "SAMPLE",
            ["견본품", "관세"],
        )
        ctx = manager.get_context("s1")
        assert ctx[0]["entities"] == ["견본품", "관세"]

    def test_add_turn_empty_session_id_raises(self, manager):
        with pytest.raises(ValueError):
            manager.add_turn("", "q", "r", "GENERAL", [])

    def test_turn_index_increments(self, manager):
        for i in range(3):
            manager.add_turn("s1", f"q{i}", f"r{i}", "GENERAL", [])
        ctx = manager.get_context("s1")
        assert [t["turn_index"] for t in ctx] == [0, 1, 2]


# ---------------------------------------------------------------------------
# Context retrieval
# ---------------------------------------------------------------------------


class TestContextRetrieval:
    def test_get_context_empty(self, manager):
        assert manager.get_context("unknown") == []

    def test_get_context_returns_chronological(self, manager):
        for i in range(5):
            manager.add_turn("s1", f"q{i}", f"r{i}", "GENERAL", [])
        ctx = manager.get_context("s1", n=10)
        assert [t["query"] for t in ctx] == [f"q{i}" for i in range(5)]

    def test_get_context_limit(self, manager):
        for i in range(10):
            manager.add_turn("s1", f"q{i}", f"r{i}", "GENERAL", [])
        ctx = manager.get_context("s1", n=3)
        # Should return the most recent 3 in chronological order
        assert len(ctx) == 3
        assert [t["query"] for t in ctx] == ["q7", "q8", "q9"]

    def test_get_context_isolated_by_session(self, manager):
        manager.add_turn("s1", "a", "b", "GENERAL", [])
        manager.add_turn("s2", "c", "d", "GENERAL", [])
        ctx1 = manager.get_context("s1")
        ctx2 = manager.get_context("s2")
        assert len(ctx1) == 1 and len(ctx2) == 1
        assert ctx1[0]["query"] == "a"
        assert ctx2[0]["query"] == "c"

    def test_get_context_non_positive_n(self, manager):
        manager.add_turn("s1", "a", "b", "GENERAL", [])
        assert manager.get_context("s1", n=0) == []


# ---------------------------------------------------------------------------
# Topic shift detection
# ---------------------------------------------------------------------------


class TestTopicShift:
    def test_no_history_no_shift(self, manager):
        assert manager.detect_topic_shift("s1", "반입 방법을 알려주세요") is False

    def test_same_topic_no_shift(self, manager):
        manager.add_turn("s1", "반입 방법은?", "...", "IMPORT_EXPORT", [])
        assert (
            manager.detect_topic_shift("s1", "반입 시 필요한 물품검사는?") is False
        )

    def test_different_topic_shift(self, manager):
        manager.add_turn("s1", "반입 방법은?", "...", "IMPORT_EXPORT", [])
        manager.add_turn("s1", "반출 절차는?", "...", "IMPORT_EXPORT", [])
        # Switch to a very different category
        assert (
            manager.detect_topic_shift(
                "s1", "담당자 연락처를 알려주세요"
            )
            is True
        )


# ---------------------------------------------------------------------------
# Followup generation
# ---------------------------------------------------------------------------


class TestFollowup:
    def test_followup_empty_session(self, manager):
        q = manager.generate_followup_question("s-empty")
        assert isinstance(q, str) and q

    def test_followup_uses_category_template(self, manager):
        manager.add_turn("s1", "특허 신청은?", "...", "LICENSE", [])
        q = manager.generate_followup_question("s1")
        assert "특허" in q

    def test_followup_uses_entity(self, manager):
        manager.add_turn(
            "s1", "견본품 관세는?", "면제 가능", "SAMPLE", ["홍보용 샘플"]
        )
        q = manager.generate_followup_question("s1")
        assert "홍보용 샘플" in q

    def test_followup_dict_entities(self, manager):
        manager.add_turn(
            "s1",
            "전시 가능 여부",
            "가능",
            "EXHIBITION",
            {"item": "전시물A"},
        )
        q = manager.generate_followup_question("s1")
        assert isinstance(q, str) and q


# ---------------------------------------------------------------------------
# Topic tracker
# ---------------------------------------------------------------------------


class TestTopicTracker:
    def test_track_and_get_path(self, tracker):
        tracker.track("s1", "GENERAL")
        tracker.track("s1", "IMPORT_EXPORT")
        assert tracker.get_topic_path("s1") == ["GENERAL", "IMPORT_EXPORT"]

    def test_coherent_single_topic(self, tracker):
        for _ in range(4):
            tracker.track("s1", "LICENSE")
        assert tracker.is_coherent("s1") is True

    def test_incoherent_mixed_topics(self, tracker):
        cats = ["GENERAL", "IMPORT_EXPORT", "LICENSE", "CONTACT", "SAMPLE"]
        for c in cats:
            tracker.track("s1", c)
        assert tracker.is_coherent("s1") is False

    def test_reset_clears_path(self, tracker):
        tracker.track("s1", "GENERAL")
        tracker.reset("s1")
        assert tracker.get_topic_path("s1") == []

    def test_thread_safety(self, tracker):
        def worker(cat):
            for _ in range(50):
                tracker.track("s1", cat)

        threads = [
            threading.Thread(target=worker, args=("A",)),
            threading.Thread(target=worker, args=("B",)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(tracker.get_topic_path("s1")) == 100


# ---------------------------------------------------------------------------
# Summary and reset
# ---------------------------------------------------------------------------


class TestSummaryAndReset:
    def test_summary_empty_session(self, manager):
        s = manager.get_conversation_summary("nobody")
        assert s["turn_count"] == 0
        assert s["dominant_category"] is None

    def test_summary_with_turns(self, manager):
        manager.add_turn("s1", "반입?", "...", "IMPORT_EXPORT", [])
        manager.add_turn("s1", "반출?", "...", "IMPORT_EXPORT", [])
        manager.add_turn("s1", "특허?", "...", "LICENSE", [])
        s = manager.get_conversation_summary("s1")
        assert s["turn_count"] == 3
        assert s["dominant_category"] == "IMPORT_EXPORT"
        assert s["first_query"] == "반입?"
        assert s["last_query"] == "특허?"

    def test_reset_context_removes_rows(self, manager):
        manager.add_turn("s1", "q", "r", "GENERAL", [])
        manager.add_turn("s1", "q2", "r2", "GENERAL", [])
        deleted = manager.reset_context("s1")
        assert deleted == 2
        assert manager.get_context("s1") == []
        assert manager.topic_tracker.get_topic_path("s1") == []


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


class TestApiEndpoints:
    def test_conversation_summary_endpoint(self, client):
        from web_server import conversation_manager_v3

        sid = f"api-test-{int(time.time() * 1000)}"
        conversation_manager_v3.add_turn(
            sid, "반입 절차?", "세관 신고...", "IMPORT_EXPORT", []
        )
        res = client.get(f"/api/session/{sid}/conversation-summary")
        assert res.status_code == 200
        data = res.get_json()
        assert data["turn_count"] == 1
        assert data["dominant_category"] == "IMPORT_EXPORT"
        conversation_manager_v3.reset_context(sid)

    def test_topic_path_endpoint(self, client):
        from web_server import conversation_manager_v3

        sid = f"api-test-path-{int(time.time() * 1000)}"
        conversation_manager_v3.add_turn(sid, "반입?", "...", "IMPORT_EXPORT", [])
        conversation_manager_v3.add_turn(sid, "반출?", "...", "IMPORT_EXPORT", [])
        res = client.get(f"/api/session/{sid}/topic-path")
        assert res.status_code == 200
        data = res.get_json()
        assert data["session_id"] == sid
        assert data["topic_path"] == ["IMPORT_EXPORT", "IMPORT_EXPORT"]
        assert data["coherent"] is True
        assert data["length"] == 2
        conversation_manager_v3.reset_context(sid)

    def test_followup_endpoint(self, client):
        from web_server import conversation_manager_v3

        sid = f"api-test-followup-{int(time.time() * 1000)}"
        conversation_manager_v3.add_turn(sid, "특허?", "...", "LICENSE", [])
        res = client.post(f"/api/session/{sid}/followup")
        assert res.status_code == 200
        data = res.get_json()
        assert data["session_id"] == sid
        assert isinstance(data["followup"], str) and data["followup"]
        conversation_manager_v3.reset_context(sid)
