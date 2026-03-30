"""감정 분석 모듈 테스트."""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.sentiment_analyzer import SentimentAnalyzer


@pytest.fixture
def analyzer():
    """임시 DB로 SentimentAnalyzer 인스턴스를 생성한다."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_sentiment.db")
        sa = SentimentAnalyzer(db_path=db_path)
        yield sa
        sa.close()


# --- 긍정 감정 감지 ---

class TestPositiveDetection:
    """긍정 감정 감지 테스트."""

    def test_simple_positive(self, analyzer):
        result = analyzer.analyze("감사합니다 도움이 됐어요")
        assert result["sentiment"] == "positive"
        assert result["score"] > 0

    def test_positive_with_thanks(self, analyzer):
        result = analyzer.analyze("친절하게 답변해주셔서 고마워요")
        assert result["sentiment"] == "positive"

    def test_positive_with_satisfaction(self, analyzer):
        result = analyzer.analyze("정확한 답변이에요 만족합니다")
        assert result["sentiment"] == "positive"
        assert result["score"] > 0

    def test_positive_keywords_present(self, analyzer):
        result = analyzer.analyze("훌륭한 서비스입니다")
        assert result["sentiment"] == "positive"
        assert len(result["keywords"]) > 0

    def test_positive_confidence(self, analyzer):
        result = analyzer.analyze("좋아요 감사해요 편리해요")
        assert result["confidence"] > 0.5


# --- 부정 감정 감지 ---

class TestNegativeDetection:
    """부정 감정 감지 테스트."""

    def test_simple_negative(self, analyzer):
        result = analyzer.analyze("불만이 많아요 답답해요")
        assert result["sentiment"] == "negative"
        assert result["score"] < 0

    def test_negative_complaint(self, analyzer):
        result = analyzer.analyze("서비스가 불편하고 짜증나요")
        assert result["sentiment"] == "negative"

    def test_negative_frustration(self, analyzer):
        result = analyzer.analyze("문제가 해결이 안돼서 화가 나요")
        assert result["sentiment"] == "negative"
        assert result["score"] < 0

    def test_negative_keywords(self, analyzer):
        result = analyzer.analyze("불합리한 처리에 실망했습니다")
        assert result["sentiment"] == "negative"
        assert len(result["keywords"]) > 0

    def test_very_negative(self, analyzer):
        result = analyzer.analyze("최악이에요 엉망이고 형편없어요 불만입니다")
        assert result["sentiment"] == "negative"
        assert result["score"] < -0.5


# --- 중립 감정 감지 ---

class TestNeutralDetection:
    """중립 감정 감지 테스트."""

    def test_neutral_question(self, analyzer):
        result = analyzer.analyze("보세전시장 운영시간이 어떻게 되나요")
        assert result["sentiment"] == "neutral"

    def test_empty_text(self, analyzer):
        result = analyzer.analyze("")
        assert result["sentiment"] == "neutral"
        assert result["score"] == 0.0

    def test_whitespace_only(self, analyzer):
        result = analyzer.analyze("   ")
        assert result["sentiment"] == "neutral"

    def test_neutral_score_range(self, analyzer):
        result = analyzer.analyze("서류 제출 방법을 알려주세요")
        assert -0.1 <= result["score"] <= 0.1


# --- 부정어(negation) 처리 ---

class TestNegationHandling:
    """부정어 처리 테스트."""

    def test_negation_of_positive(self, analyzer):
        """'안 좋아' → negative"""
        result = analyzer.analyze("안 좋아요")
        assert result["sentiment"] == "negative"
        assert result["score"] < 0

    def test_negation_of_negative(self, analyzer):
        """'불만 없어' → positive"""
        result = analyzer.analyze("불만 없어요")
        assert result["sentiment"] == "positive"
        assert result["score"] > 0

    def test_not_difficult(self, analyzer):
        """'안 어려워' → positive (부정의 부정)"""
        result = analyzer.analyze("안 어려워요")
        assert result["sentiment"] == "positive"

    def test_no_problem(self, analyzer):
        """'문제 없어' → positive"""
        result = analyzer.analyze("문제 없어요")
        assert result["sentiment"] == "positive"


# --- 강조어(intensifier) 처리 ---

class TestIntensifiers:
    """강조어 처리 테스트."""

    def test_very_positive(self, analyzer):
        result_plain = analyzer.analyze("좋아요")
        result_intense = analyzer.analyze("매우 좋아요")
        # 강조어가 있으면 점수 절대값이 더 커야 함
        assert abs(result_intense["score"]) >= abs(result_plain["score"])

    def test_really_negative(self, analyzer):
        result_plain = analyzer.analyze("불편해요")
        result_intense = analyzer.analyze("정말 불편해요")
        assert abs(result_intense["score"]) >= abs(result_plain["score"])

    def test_truly_negative(self, analyzer):
        result = analyzer.analyze("진짜 답답해요")
        assert result["sentiment"] == "negative"
        assert result["score"] < 0

    def test_extremely_positive(self, analyzer):
        result = analyzer.analyze("너무 감사합니다")
        assert result["sentiment"] == "positive"

    def test_multiple_intensifiers(self, analyzer):
        result = analyzer.analyze("정말 매우 좋아요")
        assert result["sentiment"] == "positive"
        assert result["score"] > 0


# --- 톤 조절 ---

class TestToneAdjustment:
    """답변 톤 조절 테스트."""

    def test_negative_tone_prefix(self, analyzer):
        sentiment = {"sentiment": "negative", "score": -0.4}
        adjusted = analyzer.adjust_response_tone("원래 답변입니다.", sentiment)
        assert "죄송합니다" in adjusted
        assert "원래 답변입니다." in adjusted

    def test_very_negative_tone_prefix(self, analyzer):
        sentiment = {"sentiment": "negative", "score": -0.8}
        adjusted = analyzer.adjust_response_tone("원래 답변입니다.", sentiment)
        assert "정말 죄송합니다" in adjusted

    def test_positive_tone_prefix(self, analyzer):
        sentiment = {"sentiment": "positive", "score": 0.5}
        adjusted = analyzer.adjust_response_tone("원래 답변입니다.", sentiment)
        assert "감사합니다" in adjusted
        assert "원래 답변입니다." in adjusted

    def test_neutral_no_change(self, analyzer):
        sentiment = {"sentiment": "neutral", "score": 0.0}
        adjusted = analyzer.adjust_response_tone("원래 답변입니다.", sentiment)
        assert adjusted == "원래 답변입니다."

    def test_empty_answer(self, analyzer):
        sentiment = {"sentiment": "negative", "score": -0.5}
        adjusted = analyzer.adjust_response_tone("", sentiment)
        assert adjusted == ""


# --- 에스컬레이션 트리거 ---

class TestEscalation:
    """자동 에스컬레이션 트리거 테스트."""

    def test_should_escalate_very_negative(self, analyzer):
        result = {"sentiment": "negative", "score": -0.8}
        assert analyzer.should_escalate(result) is True

    def test_should_not_escalate_mild_negative(self, analyzer):
        result = {"sentiment": "negative", "score": -0.3}
        assert analyzer.should_escalate(result) is False

    def test_should_not_escalate_positive(self, analyzer):
        result = {"sentiment": "positive", "score": 0.5}
        assert analyzer.should_escalate(result) is False

    def test_should_not_escalate_neutral(self, analyzer):
        result = {"sentiment": "neutral", "score": 0.0}
        assert analyzer.should_escalate(result) is False

    def test_escalation_threshold(self, analyzer):
        # score exactly at -0.6 should NOT escalate (< -0.6 required)
        assert analyzer.should_escalate({"score": -0.6}) is False
        assert analyzer.should_escalate({"score": -0.61}) is True


# --- DB 저장 및 통계 ---

class TestStorageAndStats:
    """DB 저장 및 통계 테스트."""

    def test_analyze_and_store(self, analyzer):
        result = analyzer.analyze_and_store("감사합니다", session_id="sess1")
        assert result["sentiment"] == "positive"
        # DB에 저장되었는지 확인
        stats = analyzer.get_sentiment_stats(session_id="sess1")
        assert stats["total"] == 1

    def test_stats_distribution(self, analyzer):
        analyzer.analyze_and_store("감사합니다", session_id="sess2")
        analyzer.analyze_and_store("불만이에요", session_id="sess2")
        analyzer.analyze_and_store("운영시간 알려주세요", session_id="sess2")
        stats = analyzer.get_sentiment_stats(session_id="sess2")
        assert stats["total"] == 3
        assert stats["distribution"]["positive"] >= 1
        assert stats["distribution"]["negative"] >= 1

    def test_stats_all_sessions(self, analyzer):
        analyzer.analyze_and_store("좋아요", session_id="a")
        analyzer.analyze_and_store("나빠요", session_id="b")
        stats = analyzer.get_sentiment_stats()
        assert stats["total"] == 2

    def test_history(self, analyzer):
        analyzer.analyze_and_store("감사합니다", session_id="h1")
        analyzer.analyze_and_store("불만이에요", session_id="h1")
        history = analyzer.get_sentiment_history(session_id="h1")
        assert len(history) == 2

    def test_history_limit(self, analyzer):
        for i in range(10):
            analyzer.analyze_and_store(f"질문 {i}", session_id="lim")
        history = analyzer.get_sentiment_history(session_id="lim", limit=3)
        assert len(history) == 3


# --- API 엔드포인트 ---

class TestSentimentAPI:
    """감정 분석 API 엔드포인트 테스트."""

    @pytest.fixture
    def client(self):
        from web_server import app
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_chat_includes_sentiment(self, client):
        res = client.post("/api/chat", json={"query": "감사합니다 좋아요"})
        assert res.status_code == 200
        data = res.get_json()
        assert "sentiment" in data
        assert data["sentiment"]["sentiment"] in ("positive", "negative", "neutral")
        assert "score" in data["sentiment"]
        assert "confidence" in data["sentiment"]

    def test_chat_negative_sentiment_escalation(self, client):
        res = client.post("/api/chat", json={
            "query": "최악이에요 불만이 너무 많고 엉망이에요 형편없어요 답답해요 화나요"
        })
        assert res.status_code == 200
        data = res.get_json()
        assert data["sentiment"]["sentiment"] == "negative"
        assert data["is_escalation"] is True

    def test_admin_sentiment_stats(self, client):
        # 인증 없이 접근 시 401 또는 200 (테스트 환경에 따라)
        res = client.get("/api/admin/sentiment")
        # 인증 필요 엔드포인트이므로 401 가능
        assert res.status_code in (200, 401, 403)

    def test_admin_sentiment_history(self, client):
        res = client.get("/api/admin/sentiment/history?session_id=test")
        assert res.status_code in (200, 401, 403)
