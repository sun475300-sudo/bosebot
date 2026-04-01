"""사용자 세분화 테스트."""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.user_segment import TermComplexityScorer, UserSegmenter


@pytest.fixture
def scorer():
    return TermComplexityScorer()


@pytest.fixture
def segmenter(tmp_path):
    db_path = str(tmp_path / "test_segments.db")
    return UserSegmenter(db_path=db_path)


# --- TermComplexityScorer ---


class TestTermComplexityScorer:
    def test_empty_query_returns_zero(self, scorer):
        assert scorer.score_query("") == 0.0
        assert scorer.score_query("   ") == 0.0

    def test_simple_query_low_score(self, scorer):
        score = scorer.score_query("보세전시장이 뭐예요?")
        # Has one legal term but is a simple question
        assert 0.0 <= score <= 1.0

    def test_complex_query_high_score(self, scorer):
        query = "관세법 제190조에 따른 보세전시장 특허보세구역의 장치기간 연장 절차와 관세감면 요건은?"
        score = scorer.score_query(query)
        assert score >= 0.4

    def test_article_reference_increases_score(self, scorer):
        simple = "보세전시장 허가 방법"
        with_article = "관세법 제190조에 따른 보세전시장 허가 방법"
        assert scorer.score_query(with_article) > scorer.score_query(simple)

    def test_score_bounded_zero_to_one(self, scorer):
        queries = [
            "",
            "안녕",
            "보세전시장이 뭐예요?",
            "관세법 제190조 제1항 보세구역 특허보세구역 관세감면 원산지증명 FTA HS코드 시행령 제50조",
        ]
        for q in queries:
            score = scorer.score_query(q)
            assert 0.0 <= score <= 1.0, f"Score {score} out of bounds for: {q}"

    def test_has_legal_terms(self, scorer):
        assert scorer.has_legal_terms("관세법에 대해 알려주세요")
        assert not scorer.has_legal_terms("오늘 날씨 어때요?")

    def test_has_article_references(self, scorer):
        assert scorer.has_article_references("제190조에 따르면")
        assert not scorer.has_article_references("일반적인 질문입니다")

    def test_has_jargon(self, scorer):
        assert scorer.has_jargon("보증금 납부 방법")
        assert not scorer.has_jargon("안녕하세요")

    def test_multiple_legal_terms_higher_score(self, scorer):
        one_term = "관세법 관련 질문"
        many_terms = "관세법 보세구역 통관 관세감면 원산지증명 관련 질문"
        assert scorer.score_query(many_terms) > scorer.score_query(one_term)


# --- UserSegmenter ---


class TestUserSegmenter:
    def test_classify_new_user_simple_query(self, segmenter):
        segment = segmenter.classify_user("session-1", "보세전시장이 뭐예요?")
        assert segment in ("beginner", "intermediate", "expert")

    def test_classify_empty_session_returns_beginner(self, segmenter):
        assert segmenter.classify_user("", "질문") == "beginner"
        assert segmenter.classify_user("s1", "") == "beginner"

    def test_get_segment_unknown_session(self, segmenter):
        assert segmenter.get_segment("nonexistent") is None

    def test_get_segment_after_classify(self, segmenter):
        segmenter.classify_user("session-2", "보세전시장이 뭐예요?")
        segment = segmenter.get_segment("session-2")
        assert segment is not None
        assert segment in ("beginner", "intermediate", "expert")

    def test_expert_classification_with_complex_queries(self, segmenter):
        complex_queries = [
            "관세법 제190조에 따른 보세전시장 특허보세구역의 장치기간 연장 시행령 관세감면 요건",
            "FTA 원산지결정기준에 따른 HS코드 품목분류 관세율 적용 시 관세평가 과세가격 산정",
            "수정신고와 경정청구 절차에서 가산세 부과 기준과 심사청구 불복 방법",
        ]
        for q in complex_queries:
            segmenter.classify_user("expert-session", q)

        segment = segmenter.get_segment("expert-session")
        assert segment == "expert"

    def test_beginner_classification_with_simple_queries(self, segmenter):
        simple_queries = [
            "보세전시장이 뭐예요?",
            "어떻게 신청하나요?",
            "잘 모르겠는데 알려주세요",
        ]
        for q in simple_queries:
            segmenter.classify_user("beginner-session", q)

        segment = segmenter.get_segment("beginner-session")
        assert segment == "beginner"

    def test_segment_evolves_over_time(self, segmenter):
        # Start with simple queries
        segmenter.classify_user("evolving", "보세전시장이 뭐예요?")
        first = segmenter.get_segment("evolving")

        # Add complex queries
        for _ in range(5):
            segmenter.classify_user(
                "evolving",
                "관세법 제190조 보세구역 특허 장치기간 시행령 관세감면 원산지 FTA HS코드 품목분류",
            )

        later = segmenter.get_segment("evolving")
        # Should have moved toward expert
        segments_order = {"beginner": 0, "intermediate": 1, "expert": 2}
        assert segments_order[later] >= segments_order[first]

    def test_get_segment_info(self, segmenter):
        segmenter.classify_user("info-session", "관세법 제190조 질문")
        info = segmenter.get_segment_info("info-session")
        assert info is not None
        assert info["session_id"] == "info-session"
        assert "segment" in info
        assert "query_count" in info
        assert info["query_count"] == 1
        assert "avg_complexity" in info
        assert "created_at" in info
        assert "updated_at" in info

    def test_get_segment_info_unknown(self, segmenter):
        assert segmenter.get_segment_info("unknown") is None
        assert segmenter.get_segment_info("") is None


# --- adjust_response_depth ---


class TestAdjustResponseDepth:
    def test_beginner_adds_suffix(self, segmenter):
        answer = "보세전시장은 관세법 제190조에 따른 시설입니다."
        adjusted = segmenter.adjust_response_depth(answer, "beginner")
        assert "참고" in adjusted
        assert "편하게 질문" in adjusted

    def test_beginner_adds_law_explanation(self, segmenter):
        answer = "관세법 제190조에 의해 규정됩니다."
        adjusted = segmenter.adjust_response_depth(answer, "beginner")
        assert "관련 법률 규정" in adjusted

    def test_intermediate_returns_unchanged(self, segmenter):
        answer = "보세전시장은 관세법 제190조에 따른 시설입니다."
        adjusted = segmenter.adjust_response_depth(answer, "intermediate")
        assert adjusted == answer

    def test_expert_highlights_citations(self, segmenter):
        answer = "관세법 제190조에 따라 처리됩니다."
        adjusted = segmenter.adjust_response_depth(answer, "expert")
        assert "【관세법 제190조】" in adjusted

    def test_empty_answer_returns_empty(self, segmenter):
        assert segmenter.adjust_response_depth("", "beginner") == ""
        assert segmenter.adjust_response_depth("", "expert") == ""


# --- get_segment_stats ---


class TestSegmentStats:
    def test_empty_stats(self, segmenter):
        stats = segmenter.get_segment_stats()
        assert stats["total"] == 0
        assert stats["beginner"] == 0
        assert stats["intermediate"] == 0
        assert stats["expert"] == 0

    def test_stats_after_classification(self, segmenter):
        segmenter.classify_user("s1", "뭐예요?")
        segmenter.classify_user("s2", "어떻게 하나요?")
        stats = segmenter.get_segment_stats()
        assert stats["total"] == 2


# --- API Endpoints ---


class TestSegmentAPI:
    @pytest.fixture
    def client(self):
        from web_server import app

        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_chat_includes_segment(self, client):
        res = client.post(
            "/api/chat",
            json={"query": "보세전시장이 뭐예요?", "session_id": "api-test-seg"},
        )
        assert res.status_code == 200
        data = res.get_json()
        assert "user_segment" in data
        assert data["user_segment"] in ("beginner", "intermediate", "expert")

    def test_chat_without_session_has_null_segment(self, client):
        res = client.post(
            "/api/chat",
            json={"query": "보세전시장이 뭐예요?"},
        )
        assert res.status_code == 200
        data = res.get_json()
        assert "user_segment" in data
        assert data["user_segment"] is None

    def test_admin_segments_stats(self, client):
        # First classify a user to populate data
        client.post(
            "/api/chat",
            json={"query": "뭐예요?", "session_id": "stats-test"},
        )
        res = client.get(
            "/api/admin/segments",
            headers={"Authorization": "Bearer test"},
        )
        assert res.status_code == 200
        data = res.get_json()
        assert "total" in data
        assert "beginner" in data
        assert "intermediate" in data
        assert "expert" in data

    def test_admin_segment_info(self, client):
        # First classify
        client.post(
            "/api/chat",
            json={"query": "관세법 제190조 보세구역 질문", "session_id": "info-api-test"},
        )
        res = client.get(
            "/api/admin/segments/info-api-test",
            headers={"Authorization": "Bearer test"},
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["session_id"] == "info-api-test"
        assert "segment" in data

    def test_admin_segment_info_not_found(self, client):
        res = client.get(
            "/api/admin/segments/nonexistent-session",
            headers={"Authorization": "Bearer test"},
        )
        assert res.status_code == 404
