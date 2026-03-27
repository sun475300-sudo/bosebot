"""세션 관리 및 멀티턴 대화 테스트."""

import time

import pytest

from src.session import Session, SessionManager, SESSION_TIMEOUT_SECONDS, _is_positive_response
from src.chatbot import BondedExhibitionChatbot


# ---------------------------------------------------------------------------
# Session 단위 테스트
# ---------------------------------------------------------------------------

class TestSession:
    """Session 클래스 단위 테스트."""

    def test_create_session(self):
        session = Session(session_id="test-1")
        assert session.session_id == "test-1"
        assert session.history == []
        assert session.pending_confirmations == []
        assert session.confirmed == {}
        assert session.context == {}

    def test_add_turn(self):
        session = Session(session_id="test-1")
        session.add_turn("질문1", "답변1")
        assert len(session.history) == 1
        assert session.history[0]["query"] == "질문1"
        assert session.history[0]["answer"] == "답변1"

    def test_add_multiple_turns(self):
        session = Session(session_id="test-1")
        session.add_turn("질문1", "답변1")
        session.add_turn("질문2", "답변2")
        assert len(session.history) == 2

    def test_has_pending_empty(self):
        session = Session(session_id="test-1")
        assert session.has_pending() is False

    def test_has_pending_with_items(self):
        session = Session(session_id="test-1")
        session.set_pending_confirmations([
            {"question": "물품은 외국물품인가요?", "why": "이유"},
        ])
        assert session.has_pending() is True

    def test_set_pending_confirmations(self):
        session = Session(session_id="test-1")
        confirmations = [
            {"question": "Q1", "why": "R1"},
            {"question": "Q2", "why": "R2"},
        ]
        session.set_pending_confirmations(confirmations)
        assert len(session.pending_confirmations) == 2

    def test_process_confirmation_positive(self):
        session = Session(session_id="test-1")
        session.set_pending_confirmations([
            {"question": "Q1", "why": "R1"},
            {"question": "Q2", "why": "R2"},
        ])
        next_q = session.process_confirmation_response("네")
        assert next_q is not None
        assert next_q["question"] == "Q2"
        assert session.confirmed["Q1"] is True

    def test_process_confirmation_negative(self):
        session = Session(session_id="test-1")
        session.set_pending_confirmations([
            {"question": "Q1", "why": "R1"},
            {"question": "Q2", "why": "R2"},
        ])
        next_q = session.process_confirmation_response("아니요")
        assert next_q is not None
        assert session.confirmed["Q1"] is False

    def test_process_confirmation_last_returns_none(self):
        session = Session(session_id="test-1")
        session.set_pending_confirmations([
            {"question": "Q1", "why": "R1"},
        ])
        next_q = session.process_confirmation_response("네")
        assert next_q is None
        assert session.has_pending() is False

    def test_process_confirmation_empty(self):
        session = Session(session_id="test-1")
        assert session.process_confirmation_response("네") is None

    def test_is_expired_false(self):
        session = Session(session_id="test-1")
        assert session.is_expired() is False

    def test_is_expired_true(self):
        session = Session(session_id="test-1")
        expired_time = time.time() + SESSION_TIMEOUT_SECONDS + 1
        assert session.is_expired(now=expired_time) is True

    def test_to_dict(self):
        session = Session(session_id="test-1")
        session.add_turn("q", "a")
        d = session.to_dict()
        assert d["session_id"] == "test-1"
        assert len(d["history"]) == 1
        assert "created_at" in d
        assert "last_active" in d


# ---------------------------------------------------------------------------
# SessionManager 단위 테스트
# ---------------------------------------------------------------------------

class TestSessionManager:
    """SessionManager 클래스 단위 테스트."""

    def test_create_session(self):
        mgr = SessionManager()
        session = mgr.create_session()
        assert session is not None
        assert session.session_id is not None

    def test_get_session(self):
        mgr = SessionManager()
        session = mgr.create_session()
        retrieved = mgr.get_session(session.session_id)
        assert retrieved is not None
        assert retrieved.session_id == session.session_id

    def test_get_nonexistent_session(self):
        mgr = SessionManager()
        assert mgr.get_session("nonexistent-id") is None

    def test_delete_session(self):
        mgr = SessionManager()
        session = mgr.create_session()
        assert mgr.delete_session(session.session_id) is True
        assert mgr.get_session(session.session_id) is None

    def test_delete_nonexistent(self):
        mgr = SessionManager()
        assert mgr.delete_session("nonexistent") is False

    def test_active_count(self):
        mgr = SessionManager()
        assert mgr.active_count() == 0
        mgr.create_session()
        mgr.create_session()
        assert mgr.active_count() == 2

    def test_expired_session_returns_none(self):
        mgr = SessionManager()
        session = mgr.create_session()
        # 세션을 과거로 만료시킴
        session.last_active = time.time() - SESSION_TIMEOUT_SECONDS - 1
        assert mgr.get_session(session.session_id) is None
        assert mgr.active_count() == 0

    def test_cleanup_expired(self):
        mgr = SessionManager()
        s1 = mgr.create_session()
        s2 = mgr.create_session()
        s1.last_active = time.time() - SESSION_TIMEOUT_SECONDS - 1
        cleaned = mgr.cleanup_expired()
        assert cleaned == 1
        assert mgr.active_count() == 1
        assert mgr.get_session(s2.session_id) is not None


# ---------------------------------------------------------------------------
# 긍정/부정 응답 파싱 테스트
# ---------------------------------------------------------------------------

class TestIsPositiveResponse:
    def test_positive_keywords(self):
        for word in ["네", "예", "맞습니다", "맞아요", "yes", "y", "넵"]:
            assert _is_positive_response(word) is True, f"'{word}' should be positive"

    def test_negative_keywords(self):
        for word in ["아니요", "아니오", "아닙니다", "no", "n", "아뇨"]:
            assert _is_positive_response(word) is False, f"'{word}' should be negative"

    def test_default_is_positive(self):
        assert _is_positive_response("잘 모르겠어요") is True


# ---------------------------------------------------------------------------
# 멀티턴 대화 통합 테스트
# ---------------------------------------------------------------------------

class TestMultiTurnConversation:
    """챗봇 멀티턴 대화 흐름 통합 테스트."""

    @pytest.fixture
    def chatbot(self):
        return BondedExhibitionChatbot()

    def test_session_multiturn_flow(self, chatbot):
        """질문 -> 확인질문 -> 응답 -> 맞춤답변 전체 흐름."""
        # 1. 세션 생성
        session = chatbot.session_manager.create_session()
        sid = session.session_id

        # 2. 초기 질문 (확인 질문이 있는 카테고리)
        response1 = chatbot.process_query("보세전시장에서 물품을 판매할 수 있나요?", session_id=sid)
        # 세션이 있고 확인 질문이 있으면 확인 질문으로 응답
        session = chatbot.session_manager.get_session(sid)
        assert session is not None

        if session.has_pending():
            # 확인 질문이 포함된 응답
            assert "확인" in response1

            # 3. 확인 질문에 응답
            pending_count = len(session.pending_confirmations)
            for i in range(pending_count):
                response = chatbot.process_query("네", session_id=sid)
                session = chatbot.session_manager.get_session(sid)
                if session.has_pending():
                    assert "다음 질문" in response or "확인" in response
                else:
                    # 마지막 확인 후 맞춤 답변
                    assert "확인 결과" in response
                    break

    def test_session_without_confirmations(self, chatbot):
        """확인 질문이 없는 경우에도 세션 기록이 남는다."""
        session = chatbot.session_manager.create_session()
        sid = session.session_id

        # 에스컬레이션 전용 질문 (FAQ 매칭 없이 에스컬레이션만 트리거)
        response = chatbot.process_query("UNI-PASS 시스템 오류가 발생했습니다", session_id=sid)
        session = chatbot.session_manager.get_session(sid)
        assert len(session.history) >= 1
        # 에스컬레이션이든 FAQ든 답변이 기록됨
        assert session.history[0]["query"] == "UNI-PASS 시스템 오류가 발생했습니다"

    def test_no_session_backward_compatible(self, chatbot):
        """세션 없이 기존과 동일하게 동작한다."""
        result = chatbot.process_query("보세전시장이 무엇인가요?")
        assert "관세법 제190조" in result
        assert "안내:" in result

    def test_no_session_empty_query(self, chatbot):
        """세션 없이 빈 질문 처리."""
        result = chatbot.process_query("")
        assert "질문을 입력" in result

    def test_invalid_session_id_falls_through(self, chatbot):
        """존재하지 않는 세션 ID는 무시하고 일반 처리한다."""
        result = chatbot.process_query("보세전시장이 무엇인가요?", session_id="invalid-id")
        assert "관세법 제190조" in result

    def test_multiturn_history_recorded(self, chatbot):
        """멀티턴 대화에서 히스토리가 올바르게 기록된다."""
        session = chatbot.session_manager.create_session()
        sid = session.session_id

        chatbot.process_query("보세전시장이 무엇인가요?", session_id=sid)
        session = chatbot.session_manager.get_session(sid)
        assert len(session.history) >= 1
        assert session.history[0]["query"] == "보세전시장이 무엇인가요?"

    def test_confirmed_response_has_tailored_advice(self, chatbot):
        """모든 확인 완료 후 맞춤 안내가 포함된 답변이 생성된다."""
        session = chatbot.session_manager.create_session()
        sid = session.session_id

        # 확인 질문을 트리거하는 질문
        chatbot.process_query("전시한 물품을 현장에서 바로 판매할 수 있나요?", session_id=sid)
        session = chatbot.session_manager.get_session(sid)

        if session.has_pending():
            # 모든 확인에 대해 응답
            while session.has_pending():
                response = chatbot.process_query("네", session_id=sid)
                session = chatbot.session_manager.get_session(sid)

            # 마지막 응답에 확인 결과 포함
            assert "확인 결과" in response
            assert "예" in response


# ---------------------------------------------------------------------------
# 웹 API 세션 엔드포인트 테스트
# ---------------------------------------------------------------------------

class TestSessionAPI:
    """세션 관련 웹 API 엔드포인트 테스트."""

    @pytest.fixture
    def client(self):
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from web_server import app
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_create_session(self, client):
        res = client.post("/api/session/new")
        assert res.status_code == 201
        data = res.get_json()
        assert "session_id" in data
        assert "created_at" in data

    def test_get_session(self, client):
        # 생성
        res = client.post("/api/session/new")
        session_id = res.get_json()["session_id"]

        # 조회
        res = client.get(f"/api/session/{session_id}")
        assert res.status_code == 200
        data = res.get_json()
        assert data["session_id"] == session_id
        assert "history" in data

    def test_get_nonexistent_session(self, client):
        res = client.get("/api/session/nonexistent-id")
        assert res.status_code == 404
        data = res.get_json()
        assert "error" in data

    def test_chat_with_session(self, client):
        # 세션 생성
        res = client.post("/api/session/new")
        session_id = res.get_json()["session_id"]

        # 세션과 함께 질문
        res = client.post("/api/chat", json={
            "query": "보세전시장이 무엇인가요?",
            "session_id": session_id,
        })
        assert res.status_code == 200
        data = res.get_json()
        assert "answer" in data
        assert data["session_id"] == session_id

    def test_chat_without_session_still_works(self, client):
        res = client.post("/api/chat", json={"query": "보세전시장이 무엇인가요?"})
        assert res.status_code == 200
        data = res.get_json()
        assert "answer" in data
        # session_id는 요청에 없었으므로 응답에도 없음
        assert "session_id" not in data

    def test_multiturn_via_api(self, client):
        """API를 통한 멀티턴 대화 흐름."""
        # 세션 생성
        res = client.post("/api/session/new")
        session_id = res.get_json()["session_id"]

        # 첫 질문
        res = client.post("/api/chat", json={
            "query": "전시한 물품을 현장에서 바로 판매할 수 있나요?",
            "session_id": session_id,
        })
        data = res.get_json()
        assert "answer" in data

        # 세션 상태 확인
        res = client.get(f"/api/session/{session_id}")
        session_data = res.get_json()
        assert len(session_data["history"]) >= 1
