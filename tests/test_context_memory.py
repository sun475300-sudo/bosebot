"""컨텍스트 메모리 시스템 테스트."""

import os
import tempfile
import time

import pytest

from src.context_memory import ContextMemory, ConversationMemoryManager


@pytest.fixture
def memory(tmp_path):
    """테스트용 임시 DB를 사용하는 ContextMemory."""
    db_path = str(tmp_path / "test_memory.db")
    return ContextMemory(db_path=db_path)


@pytest.fixture
def manager(memory):
    """테스트용 ConversationMemoryManager."""
    return ConversationMemoryManager(memory)


# ---------------------------------------------------------------------------
# ContextMemory 단위 테스트
# ---------------------------------------------------------------------------


class TestContextMemoryStoreRetrieve:
    """컨텍스트 저장/조회 테스트."""

    def test_store_and_get(self, memory):
        memory.store_context("s1", "topic", "보세전시장 반입절차")
        entries = memory.get_context("s1")
        assert len(entries) == 1
        assert entries[0]["key"] == "topic"
        assert entries[0]["value"] == "보세전시장 반입절차"

    def test_get_specific_key(self, memory):
        memory.store_context("s1", "topic", "반입절차")
        memory.store_context("s1", "category", "IMPORT")
        entries = memory.get_context("s1", key="topic")
        assert len(entries) == 1
        assert entries[0]["key"] == "topic"

    def test_get_all_keys(self, memory):
        memory.store_context("s1", "topic", "반입절차")
        memory.store_context("s1", "category", "IMPORT")
        entries = memory.get_context("s1")
        assert len(entries) == 2

    def test_get_nonexistent_session(self, memory):
        entries = memory.get_context("nonexistent")
        assert entries == []

    def test_store_json_value(self, memory):
        memory.store_context("s1", "preference", {"lang": "ko", "detail": True})
        entries = memory.get_context("s1", key="preference")
        assert len(entries) == 1
        assert entries[0]["value"] == {"lang": "ko", "detail": True}

    def test_multiple_sessions_isolated(self, memory):
        memory.store_context("s1", "topic", "반입")
        memory.store_context("s2", "topic", "반출")
        s1_entries = memory.get_context("s1")
        s2_entries = memory.get_context("s2")
        assert len(s1_entries) == 1
        assert s1_entries[0]["value"] == "반입"
        assert len(s2_entries) == 1
        assert s2_entries[0]["value"] == "반출"


class TestContextMemoryTTL:
    """TTL(만료) 테스트."""

    def test_expired_entries_not_returned(self, memory):
        # TTL 0 시간 = 즉시 만료
        memory.store_context("s1", "topic", "만료될 항목", ttl_hours=0)
        time.sleep(0.01)
        entries = memory.get_context("s1")
        assert len(entries) == 0

    def test_valid_entries_returned(self, memory):
        memory.store_context("s1", "topic", "유효한 항목", ttl_hours=1)
        entries = memory.get_context("s1")
        assert len(entries) == 1

    def test_cleanup_expired(self, memory):
        memory.store_context("s1", "old", "만료", ttl_hours=0)
        memory.store_context("s1", "new", "유효", ttl_hours=24)
        time.sleep(0.01)
        deleted = memory.cleanup_expired()
        assert deleted == 1
        # 유효한 항목은 남아있어야 함
        entries = memory.get_context("s1")
        assert len(entries) == 1
        assert entries[0]["key"] == "new"


class TestContextMemoryProfile:
    """사용자 프로필 테스트."""

    def test_empty_profile(self, memory):
        profile = memory.get_user_profile("s1")
        assert profile["session_id"] == "s1"
        assert profile["topics"] == []
        assert profile["preferences"] == {}
        assert profile["total_interactions"] == 0

    def test_profile_with_topics(self, memory):
        memory.store_context("s1", "topic", "반입절차")
        memory.store_context("s1", "topic", "반입절차")
        memory.store_context("s1", "topic", "관세")
        profile = memory.get_user_profile("s1")
        assert "반입절차" in profile["topics"]
        assert "관세" in profile["topics"]
        # 빈도순: 반입절차가 첫번째
        assert profile["topics"][0] == "반입절차"
        assert profile["total_interactions"] == 3

    def test_profile_with_preferences(self, memory):
        memory.store_context("s1", "preference", {"lang": "en"})
        profile = memory.get_user_profile("s1")
        assert profile["preferences"]["lang"] == "en"


class TestContextMemorySessionDetection:
    """이전 세션 감지 테스트."""

    def test_no_previous_sessions(self, memory):
        result = memory.get_previous_sessions("s1")
        assert result == []

    def test_previous_sessions_after_merge(self, memory):
        memory.store_context("old-session", "topic", "이전 토픽")
        memory.merge_context("old-session", "new-session")
        previous = memory.get_previous_sessions("new-session")
        assert "old-session" in previous

    def test_previous_sessions_limit(self, memory):
        for i in range(10):
            memory.merge_context(f"old-{i}", "current")
        previous = memory.get_previous_sessions("current", limit=3)
        assert len(previous) == 3


class TestContextMemoryMerge:
    """세션 병합 테스트."""

    def test_merge_copies_entries(self, memory):
        memory.store_context("old", "topic", "반입")
        memory.store_context("old", "category", "IMPORT")
        count = memory.merge_context("old", "new")
        assert count == 2
        new_entries = memory.get_context("new")
        assert len(new_entries) == 2

    def test_merge_preserves_original(self, memory):
        memory.store_context("old", "topic", "반입")
        memory.merge_context("old", "new")
        old_entries = memory.get_context("old")
        assert len(old_entries) == 1

    def test_merge_skips_expired(self, memory):
        memory.store_context("old", "expired", "만료됨", ttl_hours=0)
        memory.store_context("old", "valid", "유효함", ttl_hours=24)
        time.sleep(0.01)
        count = memory.merge_context("old", "new")
        assert count == 1
        new_entries = memory.get_context("new")
        assert len(new_entries) == 1
        assert new_entries[0]["key"] == "valid"


class TestContextMemoryForget:
    """컨텍스트 삭제 테스트."""

    def test_forget_all(self, memory):
        memory.store_context("s1", "topic", "반입")
        memory.store_context("s1", "category", "IMPORT")
        deleted = memory.forget("s1")
        assert deleted == 2
        assert memory.get_context("s1") == []

    def test_forget_specific_key(self, memory):
        memory.store_context("s1", "topic", "반입")
        memory.store_context("s1", "category", "IMPORT")
        deleted = memory.forget("s1", key="topic")
        assert deleted == 1
        remaining = memory.get_context("s1")
        assert len(remaining) == 1
        assert remaining[0]["key"] == "category"

    def test_forget_nonexistent(self, memory):
        deleted = memory.forget("nonexistent")
        assert deleted == 0


# ---------------------------------------------------------------------------
# ConversationMemoryManager 테스트
# ---------------------------------------------------------------------------


class TestConversationMemoryManager:
    """ConversationMemoryManager 테스트."""

    def test_remember_topic(self, manager, memory):
        manager.remember_topic("s1", "보세전시장 반입절차", "IMPORT")
        topics = memory.get_context("s1", key="topic")
        categories = memory.get_context("s1", key="category")
        assert len(topics) == 1
        assert topics[0]["value"] == "보세전시장 반입절차"
        assert len(categories) == 1
        assert categories[0]["value"] == "IMPORT"

    def test_get_conversation_resume(self, manager):
        manager.remember_topic("s1", "보세전시장 반입절차", "IMPORT")
        resume = manager.get_conversation_resume("s1")
        assert resume is not None
        assert "보세전시장 반입절차" in resume

    def test_get_conversation_resume_no_history(self, manager):
        resume = manager.get_conversation_resume("s1")
        assert resume is None

    def test_is_returning_user_false(self, manager):
        assert manager.is_returning_user("new-user") is False

    def test_is_returning_user_with_context(self, manager):
        manager.remember_topic("s1", "반입절차", "IMPORT")
        assert manager.is_returning_user("s1") is True

    def test_is_returning_user_with_merge(self, manager, memory):
        memory.store_context("old", "topic", "이전 주제")
        memory.merge_context("old", "new")
        assert manager.is_returning_user("new") is True


# ---------------------------------------------------------------------------
# API 엔드포인트 테스트
# ---------------------------------------------------------------------------


class TestContextMemoryAPI:
    """웹 서버 API 엔드포인트 테스트."""

    @pytest.fixture
    def client(self, tmp_path):
        """Flask 테스트 클라이언트."""
        # web_server의 context_memory를 임시 DB로 교체
        import web_server
        original_memory = web_server.context_memory
        original_manager = web_server.conversation_memory_manager
        test_memory = ContextMemory(db_path=str(tmp_path / "api_test_memory.db"))
        web_server.context_memory = test_memory
        web_server.conversation_memory_manager = ConversationMemoryManager(test_memory)
        web_server.app.config["TESTING"] = True
        client = web_server.app.test_client()
        yield client, test_memory
        web_server.context_memory = original_memory
        web_server.conversation_memory_manager = original_manager

    def test_get_context_empty(self, client):
        client, memory = client
        resp = client.get("/api/session/test-session/context")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["session_id"] == "test-session"
        assert data["context"] == []

    def test_get_context_with_data(self, client):
        client, memory = client
        memory.store_context("test-session", "topic", "반입절차")
        resp = client.get("/api/session/test-session/context")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["context"]) == 1
        assert data["context"][0]["key"] == "topic"

    def test_get_context_with_key_filter(self, client):
        client, memory = client
        memory.store_context("test-session", "topic", "반입절차")
        memory.store_context("test-session", "category", "IMPORT")
        resp = client.get("/api/session/test-session/context?key=topic")
        data = resp.get_json()
        assert len(data["context"]) == 1
        assert data["context"][0]["key"] == "topic"

    def test_get_profile(self, client):
        client, memory = client
        memory.store_context("test-session", "topic", "반입절차")
        memory.store_context("test-session", "topic", "관세")
        resp = client.get("/api/session/test-session/profile")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["session_id"] == "test-session"
        assert "반입절차" in data["topics"]

    def test_delete_context(self, client):
        client, memory = client
        memory.store_context("test-session", "topic", "반입절차")
        memory.store_context("test-session", "category", "IMPORT")
        resp = client.delete(
            "/api/session/test-session/context",
            json={},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["deleted"] == 2
        # 삭제 후 빈 결과
        entries = memory.get_context("test-session")
        assert entries == []

    def test_delete_context_specific_key(self, client):
        client, memory = client
        memory.store_context("test-session", "topic", "반입절차")
        memory.store_context("test-session", "category", "IMPORT")
        resp = client.delete(
            "/api/session/test-session/context",
            json={"key": "topic"},
        )
        data = resp.get_json()
        assert data["deleted"] == 1
        remaining = memory.get_context("test-session")
        assert len(remaining) == 1
        assert remaining[0]["key"] == "category"
