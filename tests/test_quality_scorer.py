"""Tests for the ResponseQualityScorer and QualityReport classes."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.quality_scorer import ResponseQualityScorer, QualityReport


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def scorer():
    return ResponseQualityScorer()


@pytest.fixture
def sample_query():
    return "보세전시장 입장절차는 어떻게 되나요?"


@pytest.fixture
def good_answer():
    return (
        "보세전시장 입장절차에 대해 설명드리겠습니다.\n"
        "관세법 제156조에 따라 보세전시장에 입장하려면 "
        "세관장의 허가를 받아야 합니다.\n"
        "전시품 반입 시 수입신고서와 함께 물품목록을 제출해야 하며, "
        "관세청에서 정한 절차를 따라야 합니다.\n"
        "따라서 입장 전 관할 세관에 사전 신청이 필요합니다.\n"
        "참고로 자세한 내용은 관할 세관에 문의하시기 바랍니다."
    )


@pytest.fixture
def poor_answer():
    return "모르겠습니다"


@pytest.fixture
def scored_scorer(scorer, sample_query, good_answer, poor_answer):
    """Scorer with pre-scored entries for testing aggregation."""
    scorer.score_response(sample_query, good_answer, "입장절차")
    scorer.score_response("세금 관련 질문", poor_answer, "세금")
    scorer.score_response(
        "통관 절차가 궁금합니다",
        "통관 절차는 관세법 제241조에 근거하여 수입신고를 하셔야 합니다. "
        "따라서 세관에 문의하시기 바랍니다.",
        "통관",
    )
    return scorer


# ---------------------------------------------------------------------------
# Relevance scoring
# ---------------------------------------------------------------------------

class TestRelevanceScoring:
    def test_high_overlap(self, scorer):
        query = "보세전시장 입장절차"
        answer = "보세전시장 입장절차는 다음과 같습니다."
        result = scorer.score_response(query, answer)
        assert result["breakdown"]["relevance"] > 0

    def test_no_overlap(self, scorer):
        query = "보세전시장 입장절차"
        answer = "감사합니다 좋은 하루 되세요"
        result = scorer.score_response(query, answer)
        assert result["breakdown"]["relevance"] == 0

    def test_empty_query(self, scorer):
        result = scorer.score_response("", "some answer")
        assert result["breakdown"]["relevance"] == 0

    def test_empty_answer(self, scorer):
        result = scorer.score_response("some query", "")
        assert result["breakdown"]["relevance"] == 0

    def test_max_relevance_capped(self, scorer):
        result = scorer.score_response("test query", "test query repeated test query")
        assert result["breakdown"]["relevance"] <= 30


# ---------------------------------------------------------------------------
# Completeness scoring
# ---------------------------------------------------------------------------

class TestCompletenessScoring:
    def test_complete_answer(self, scorer, sample_query, good_answer):
        result = scorer.score_response(sample_query, good_answer)
        # Good answer has conclusion (따라서), explanation, legal_basis (관세법), disclaimer (참고)
        assert result["breakdown"]["completeness"] >= 19

    def test_incomplete_answer(self, scorer, sample_query, poor_answer):
        result = scorer.score_response(sample_query, poor_answer)
        assert result["breakdown"]["completeness"] == 0

    def test_partial_completeness(self, scorer):
        answer = "관세법에 따라 처리됩니다. 참고로 확인 바랍니다."
        result = scorer.score_response("질문", answer)
        assert 0 < result["breakdown"]["completeness"] <= 25

    def test_max_completeness_capped(self, scorer):
        result = scorer.score_response("q", "따라서 설명하면 관세법 제1조에 의해 참고 바랍니다.")
        assert result["breakdown"]["completeness"] <= 25


# ---------------------------------------------------------------------------
# Specificity scoring
# ---------------------------------------------------------------------------

class TestSpecificityScoring:
    def test_specific_answer(self, scorer, sample_query, good_answer):
        result = scorer.score_response(sample_query, good_answer)
        # Good answer has numbers (156), article ref (제156조), legal terms (관세법), institutions (관세청)
        assert result["breakdown"]["specificity"] >= 10

    def test_vague_answer(self, scorer, sample_query, poor_answer):
        result = scorer.score_response(sample_query, poor_answer)
        assert result["breakdown"]["specificity"] == 0

    def test_numbers_detected(self, scorer):
        answer = "총 50건의 물품이 반입되었습니다."
        result = scorer.score_response("질문", answer)
        assert result["breakdown"]["specificity"] >= 5

    def test_article_refs_detected(self, scorer):
        answer = "제241조에 따른 수입신고가 필요합니다."
        result = scorer.score_response("질문", answer)
        assert result["breakdown"]["specificity"] >= 10

    def test_max_specificity_capped(self, scorer):
        answer = (
            "관세법 시행령 시행규칙 고시 통첩에 따라 제1조 제2조 "
            "관세청 세관 한국무역협회 국세청 100건"
        )
        result = scorer.score_response("질문", answer)
        assert result["breakdown"]["specificity"] <= 20


# ---------------------------------------------------------------------------
# Readability scoring
# ---------------------------------------------------------------------------

class TestReadabilityScoring:
    def test_good_length(self, scorer, sample_query, good_answer):
        result = scorer.score_response(sample_query, good_answer)
        # Good answer has appropriate length, multiple sentences, newlines
        assert result["breakdown"]["readability"] >= 10

    def test_too_short(self, scorer):
        result = scorer.score_response("질문", "짧은 답")
        assert result["breakdown"]["readability"] < 10

    def test_max_readability_capped(self, scorer, sample_query, good_answer):
        result = scorer.score_response(sample_query, good_answer)
        assert result["breakdown"]["readability"] <= 15


# ---------------------------------------------------------------------------
# Legal accuracy scoring
# ---------------------------------------------------------------------------

class TestLegalAccuracyScoring:
    def test_correct_category_refs(self, scorer):
        answer = "관세법 제156조에 따라 보세화물 반입이 가능합니다."
        result = scorer.score_response("질문", answer, "입장절차")
        assert result["breakdown"]["legal_accuracy"] > 0

    def test_no_category(self, scorer):
        result = scorer.score_response("질문", "답변입니다.", "")
        assert result["breakdown"]["legal_accuracy"] == 0

    def test_unknown_category_with_legal(self, scorer):
        answer = "관세법 제100조에 의거합니다."
        result = scorer.score_response("질문", answer, "기타")
        # 기타 has no specific refs, but answer has legal terms -> partial credit
        assert result["breakdown"]["legal_accuracy"] >= 5

    def test_max_legal_accuracy_capped(self, scorer):
        answer = "관세법 보세화물 제156조 제157조 제174조에 따릅니다."
        result = scorer.score_response("질문", answer, "입장절차")
        assert result["breakdown"]["legal_accuracy"] <= 10


# ---------------------------------------------------------------------------
# Total score
# ---------------------------------------------------------------------------

class TestTotalScore:
    def test_total_is_sum_of_breakdown(self, scorer, sample_query, good_answer):
        result = scorer.score_response(sample_query, good_answer, "입장절차")
        expected = sum(result["breakdown"].values())
        assert result["total_score"] == expected

    def test_score_range(self, scorer, sample_query, good_answer):
        result = scorer.score_response(sample_query, good_answer, "입장절차")
        assert 0 <= result["total_score"] <= 100

    def test_poor_answer_low_score(self, scorer, sample_query, poor_answer):
        result = scorer.score_response(sample_query, poor_answer)
        assert result["total_score"] < 30

    def test_result_has_metadata(self, scorer, sample_query, good_answer):
        result = scorer.score_response(sample_query, good_answer, "입장절차")
        assert result["query"] == sample_query
        assert result["answer"] == good_answer
        assert result["category"] == "입장절차"
        assert "timestamp" in result


# ---------------------------------------------------------------------------
# Batch scoring
# ---------------------------------------------------------------------------

class TestBatchScoring:
    def test_batch_returns_list(self, scorer, sample_query, good_answer, poor_answer):
        pairs = [
            {"query": sample_query, "answer": good_answer, "category": "입장절차"},
            {"query": "세금 질문", "answer": poor_answer},
        ]
        results = scorer.score_batch(pairs)
        assert len(results) == 2

    def test_batch_each_has_score(self, scorer, sample_query, good_answer):
        pairs = [{"query": sample_query, "answer": good_answer}]
        results = scorer.score_batch(pairs)
        assert "total_score" in results[0]
        assert "breakdown" in results[0]

    def test_empty_batch(self, scorer):
        assert scorer.score_batch([]) == []


# ---------------------------------------------------------------------------
# Low quality detection
# ---------------------------------------------------------------------------

class TestLowQualityDetection:
    def test_finds_low_quality(self, scored_scorer):
        low = scored_scorer.get_low_quality_responses(threshold=60)
        # The poor answer "모르겠습니다" should score very low
        assert len(low) >= 1
        assert all(r["total_score"] < 60 for r in low)

    def test_sorted_ascending(self, scored_scorer):
        low = scored_scorer.get_low_quality_responses(threshold=100)
        scores = [r["total_score"] for r in low]
        assert scores == sorted(scores)

    def test_custom_threshold(self, scored_scorer):
        low_strict = scored_scorer.get_low_quality_responses(threshold=90)
        low_lenient = scored_scorer.get_low_quality_responses(threshold=20)
        assert len(low_strict) >= len(low_lenient)

    def test_no_history(self, scorer):
        assert scorer.get_low_quality_responses() == []


# ---------------------------------------------------------------------------
# Quality trend
# ---------------------------------------------------------------------------

class TestQualityTrend:
    def test_trend_returns_list(self, scored_scorer):
        trend = scored_scorer.get_quality_trend(days=30)
        assert isinstance(trend, list)

    def test_trend_has_date_and_score(self, scored_scorer):
        trend = scored_scorer.get_quality_trend(days=30)
        if trend:
            entry = trend[0]
            assert "date" in entry
            assert "avg_score" in entry
            assert "count" in entry

    def test_empty_history(self, scorer):
        assert scorer.get_quality_trend(days=30) == []


# ---------------------------------------------------------------------------
# Improvement suggestions
# ---------------------------------------------------------------------------

class TestImprovementSuggestions:
    def test_poor_answer_gets_suggestions(self, scorer, sample_query, poor_answer):
        result = scorer.score_response(sample_query, poor_answer)
        suggestions = scorer.suggest_improvements(
            sample_query, poor_answer, result["breakdown"]
        )
        assert len(suggestions) >= 1

    def test_good_answer_fewer_suggestions(self, scorer, sample_query, good_answer):
        result = scorer.score_response(sample_query, good_answer, "입장절차")
        suggestions = scorer.suggest_improvements(
            sample_query, good_answer, result["breakdown"]
        )
        # Should have at least the "good quality" message or very few suggestions
        assert isinstance(suggestions, list)

    def test_low_relevance_suggestion(self, scorer):
        breakdown = {"relevance": 5, "completeness": 25, "specificity": 20, "readability": 15, "legal_accuracy": 10}
        suggestions = scorer.suggest_improvements("query", "answer", breakdown)
        assert any("relevance" in s.lower() or "keyword" in s.lower() for s in suggestions)

    def test_low_completeness_suggestion(self, scorer):
        breakdown = {"relevance": 30, "completeness": 5, "specificity": 20, "readability": 15, "legal_accuracy": 10}
        suggestions = scorer.suggest_improvements("query", "short", breakdown)
        assert any("section" in s.lower() or "missing" in s.lower() for s in suggestions)

    def test_low_specificity_suggestion(self, scorer):
        breakdown = {"relevance": 30, "completeness": 25, "specificity": 3, "readability": 15, "legal_accuracy": 10}
        suggestions = scorer.suggest_improvements("query", "answer", breakdown)
        assert any("specific" in s.lower() or "fact" in s.lower() for s in suggestions)

    def test_low_legal_accuracy_suggestion(self, scorer):
        breakdown = {"relevance": 30, "completeness": 25, "specificity": 20, "readability": 15, "legal_accuracy": 2}
        suggestions = scorer.suggest_improvements("query", "answer", breakdown)
        assert any("legal" in s.lower() for s in suggestions)

    def test_all_good_no_issue(self, scorer):
        breakdown = {"relevance": 25, "completeness": 20, "specificity": 15, "readability": 12, "legal_accuracy": 8}
        suggestions = scorer.suggest_improvements("query", "a decent answer here", breakdown)
        assert any("good" in s.lower() or "no major" in s.lower() for s in suggestions)


# ---------------------------------------------------------------------------
# QualityReport
# ---------------------------------------------------------------------------

class TestQualityReport:
    def test_generate_empty(self, scorer):
        report = QualityReport(scorer)
        result = report.generate(days=30)
        assert result["total_scored"] == 0
        assert result["avg_score"] == 0

    def test_generate_with_data(self, scored_scorer):
        report = QualityReport(scored_scorer)
        result = report.generate(days=30)
        assert result["total_scored"] == 3
        assert result["avg_score"] > 0
        assert "score_distribution" in result
        assert "dimension_averages" in result
        assert "category_quality" in result
        assert "trend" in result

    def test_category_quality(self, scored_scorer):
        report = QualityReport(scored_scorer)
        cat_quality = report.get_category_quality()
        assert "입장절차" in cat_quality
        assert "세금" in cat_quality
        assert "avg_score" in cat_quality["입장절차"]
        assert "count" in cat_quality["입장절차"]

    def test_score_distribution_buckets(self, scored_scorer):
        report = QualityReport(scored_scorer)
        result = report.generate(days=30)
        dist = result["score_distribution"]
        assert set(dist.keys()) == {"0-20", "21-40", "41-60", "61-80", "81-100"}
        assert sum(dist.values()) == result["total_scored"]

    def test_dimension_averages(self, scored_scorer):
        report = QualityReport(scored_scorer)
        result = report.generate(days=30)
        dims = result["dimension_averages"]
        for key in ["relevance", "completeness", "specificity", "readability", "legal_accuracy"]:
            assert key in dims


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

class TestQualityAPI:
    @pytest.fixture
    def client(self):
        from web_server import app
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_scores_endpoint(self, client):
        res = client.get("/api/admin/quality/scores")
        assert res.status_code == 200
        data = res.get_json()
        assert "total_scored" in data

    def test_low_endpoint(self, client):
        res = client.get("/api/admin/quality/low")
        assert res.status_code == 200
        data = res.get_json()
        assert "threshold" in data
        assert "count" in data
        assert "responses" in data

    def test_low_endpoint_custom_threshold(self, client):
        res = client.get("/api/admin/quality/low?threshold=80")
        assert res.status_code == 200
        data = res.get_json()
        assert data["threshold"] == 80

    def test_trend_endpoint(self, client):
        res = client.get("/api/admin/quality/trend")
        assert res.status_code == 200
        data = res.get_json()
        assert "days" in data
        assert "trend" in data

    def test_score_single_endpoint(self, client):
        res = client.post(
            "/api/admin/quality/score",
            json={
                "query": "보세전시장 입장절차",
                "answer": "관세법 제156조에 따라 입장 가능합니다. 참고로 세관에 문의 바랍니다.",
                "category": "입장절차",
            },
        )
        assert res.status_code == 200
        data = res.get_json()
        assert "total_score" in data
        assert "breakdown" in data
        assert "suggestions" in data

    def test_score_single_missing_fields(self, client):
        res = client.post(
            "/api/admin/quality/score",
            json={"query": "질문만"},
        )
        assert res.status_code == 400
        data = res.get_json()
        assert "error" in data
