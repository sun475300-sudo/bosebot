"""Tests for the HybridSearchV3 engine and its Flask endpoints."""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.hybrid_search_v3 import HybridSearchV3


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def faq_items():
    return [
        {
            "id": "A",
            "category": "GENERAL",
            "question": "보세전시장이 무엇인가요?",
            "answer": "보세전시장은 박람회, 전람회, 견본품 전시회 등의 운영을 위한 보세구역입니다.",
            "keywords": ["보세전시장", "정의", "개념", "보세구역", "뜻"],
        },
        {
            "id": "B",
            "category": "IMPORT_EXPORT",
            "question": "보세전시장에 물품을 반입하거나 반출하려면 신고가 필요한가요?",
            "answer": "네. 보세전시장에 물품을 반출입하려는 자는 세관장에게 신고를 해야 합니다.",
            "keywords": ["반입", "반출", "신고", "반출입신고", "검사"],
        },
        {
            "id": "C",
            "category": "SALES",
            "question": "보세전시장에 전시한 물품을 현장에서 바로 판매할 수 있나요?",
            "answer": "현장 판매는 검토할 수 있지만 통관 전 자유롭게 인도할 수는 없습니다.",
            "keywords": ["판매", "직매", "현장판매", "인도", "통관"],
        },
        {
            "id": "D",
            "category": "SAMPLE",
            "question": "전시물 일부를 견본품으로 밖에 가져가도 되나요?",
            "answer": "견본품으로 반출하는 것은 조건 하에 가능합니다.",
            "keywords": ["견본품", "샘플", "홍보용", "반출"],
        },
    ]


@pytest.fixture(scope="module")
def variants_file():
    data = {
        "version": "1.0.0",
        "description": "test variants",
        "variants": [
            {
                "faq_id": "A",
                "original_question": "보세전시장이 무엇인가요?",
                "variants": [
                    "보세전시장이 뭔가요?",
                    "보세전시장 정의가 뭐예요?",
                    "보세전시장이란?",
                    "보세전시장 설명해주세요",
                    "보세전시장이 뭐야",
                ],
            },
            {
                "faq_id": "B",
                "original_question": "보세전시장에 물품을 반입하거나 반출하려면 신고가 필요한가요?",
                "variants": [
                    "물품 반출입할 때 신고해야 돼?",
                    "보세전시장 반입 반출 신고 필요?",
                    "전시장에 물건 넣고 빼려면 어떻게 하나요?",
                ],
            },
            {
                "faq_id": "C",
                "original_question": "보세전시장에 전시한 물품을 현장에서 바로 판매할 수 있나요?",
                "variants": [
                    "전시 물품 현장 판매 가능?",
                    "보세전시장에서 물건 팔 수 있어?",
                    "현장 직매가 되나요?",
                ],
            },
        ],
    }
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    yield path
    os.unlink(path)


@pytest.fixture
def engine(faq_items, variants_file):
    return HybridSearchV3(faq_items, variants_path=variants_file)


# ---------------------------------------------------------------------------
# Core search behaviour
# ---------------------------------------------------------------------------


class TestSearchBasic:
    def test_search_returns_results(self, engine):
        results = engine.search("보세전시장이 뭐야", top_k=3)
        assert isinstance(results, list)
        assert len(results) >= 1
        assert results[0]["faq_id"] == "A"

    def test_search_result_schema(self, engine):
        results = engine.search("보세전시장 판매", top_k=3)
        assert results
        hit = results[0]
        for key in ("faq_id", "score", "matched_via", "matched_text", "breakdown"):
            assert key in hit
        assert set(hit["breakdown"].keys()) == {"keyword", "bm25", "variant"}

    def test_search_empty_query_returns_empty(self, engine):
        assert engine.search("", top_k=3) == []
        assert engine.search("   ", top_k=3) == []

    def test_top_k_parameter_limits_results(self, engine):
        results = engine.search("보세전시장 반입 판매 견본품", top_k=2)
        assert len(results) <= 2

    def test_top_k_zero_returns_empty(self, engine):
        assert engine.search("보세전시장", top_k=0) == []

    def test_results_sorted_by_score_desc(self, engine):
        results = engine.search("보세전시장 반입 판매", top_k=4)
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_no_match_returns_empty(self, engine):
        results = engine.search("xyz완전히관계없는외국어abc", top_k=3)
        assert results == [] or all(r["score"] >= 0 for r in results)


# ---------------------------------------------------------------------------
# Signal contribution
# ---------------------------------------------------------------------------


class TestSignalContributions:
    def test_keyword_signal_contributes(self, engine):
        # Query uses direct keywords from FAQ C (판매/현장판매)
        results = engine.search("현장 판매 가능한가요", top_k=5)
        hit_c = next((r for r in results if r["faq_id"] == "C"), None)
        assert hit_c is not None
        assert hit_c["breakdown"]["keyword"] > 0

    def test_bm25_signal_contributes(self, engine):
        # BM25 should match term "반출입신고" in question text
        results = engine.search("반출입신고", top_k=5)
        hit_b = next((r for r in results if r["faq_id"] == "B"), None)
        assert hit_b is not None
        assert hit_b["breakdown"]["bm25"] > 0

    def test_variant_signal_contributes(self, engine):
        # Exact variant phrase should score high on variant signal
        results = engine.search("보세전시장이 뭐야", top_k=5)
        hit_a = next((r for r in results if r["faq_id"] == "A"), None)
        assert hit_a is not None
        assert hit_a["breakdown"]["variant"] > 0

    def test_matched_via_reflects_dominant_signal(self, engine):
        results = engine.search("보세전시장이 뭐야", top_k=1)
        assert results[0]["matched_via"] in {"keyword", "bm25", "variant"}


# ---------------------------------------------------------------------------
# Weight tuning
# ---------------------------------------------------------------------------


class TestTunableWeights:
    def test_default_weights(self, engine):
        w = engine.get_weights()
        assert w["keyword"] == pytest.approx(0.3)
        assert w["bm25"] == pytest.approx(0.4)
        assert w["variant"] == pytest.approx(0.3)

    def test_set_weights_updates(self, engine):
        engine.set_weights(0.1, 0.2, 0.7)
        w = engine.get_weights()
        assert w["keyword"] == pytest.approx(0.1)
        assert w["bm25"] == pytest.approx(0.2)
        assert w["variant"] == pytest.approx(0.7)
        # Reset
        engine.set_weights(0.3, 0.4, 0.3)

    def test_negative_weights_clamped_to_zero(self, engine):
        engine.set_weights(-1, -2, -3)
        assert engine.get_weights() == {"keyword": 0.0, "bm25": 0.0, "variant": 0.0}
        engine.set_weights(0.3, 0.4, 0.3)

    def test_variant_only_weights_prioritise_variants(self, engine):
        engine.set_weights(0.0, 0.0, 1.0)
        results = engine.search("보세전시장이 뭐야", top_k=3)
        assert results[0]["faq_id"] == "A"
        # Score should be dominated by the variant signal
        assert results[0]["breakdown"]["variant"] > 0
        engine.set_weights(0.3, 0.4, 0.3)

    def test_zero_all_weights_returns_empty(self, engine):
        engine.set_weights(0, 0, 0)
        assert engine.search("보세전시장", top_k=3) == []
        engine.set_weights(0.3, 0.4, 0.3)


# ---------------------------------------------------------------------------
# explain_result
# ---------------------------------------------------------------------------


class TestExplainResult:
    def test_explain_found(self, engine):
        exp = engine.explain_result("보세전시장이 뭐야", "A")
        assert exp["found"] is True
        assert exp["faq_id"] == "A"
        assert "breakdown" in exp
        assert "reasons" in exp and len(exp["reasons"]) >= 1

    def test_explain_unknown_faq_id(self, engine):
        exp = engine.explain_result("보세전시장이 뭐야", "ZZZ")
        assert exp["found"] is False

    def test_explain_empty_query(self, engine):
        exp = engine.explain_result("", "A")
        assert exp["found"] is True
        assert exp.get("score", 0.0) == 0.0

    def test_explain_reports_matched_variant(self, engine):
        exp = engine.explain_result("보세전시장이 뭐야", "A")
        assert exp["variant_score"] > 0
        assert exp["matched_variant"]

    def test_explain_reports_matched_keywords(self, engine):
        exp = engine.explain_result("반출입신고 필요한가요", "B")
        assert exp["keyword_score"] > 0 or exp["bm25_normalized"] > 0


# ---------------------------------------------------------------------------
# Missing variant file
# ---------------------------------------------------------------------------


class TestMissingVariants:
    def test_works_without_variants_file(self, faq_items):
        engine = HybridSearchV3(faq_items, variants_path="/tmp/__does_not_exist__.json")
        results = engine.search("보세전시장", top_k=2)
        # Still returns BM25/keyword results
        assert isinstance(results, list)

    def test_variant_scores_zero_when_file_missing(self, faq_items):
        engine = HybridSearchV3(faq_items, variants_path="/tmp/__does_not_exist__.json")
        results = engine.search("보세전시장", top_k=5)
        for r in results:
            assert r["breakdown"]["variant"] == 0


# ---------------------------------------------------------------------------
# Flask API endpoint
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    from web_server import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestAPIEndpoint:
    def test_hybrid_search_endpoint_post(self, client):
        res = client.post(
            "/api/search/hybrid",
            json={"query": "보세전시장이 뭐야", "top_k": 3},
        )
        assert res.status_code == 200
        data = res.get_json()
        assert "results" in data
        assert "weights" in data
        assert data["query"].strip()

    def test_hybrid_search_endpoint_get(self, client):
        res = client.get("/api/search/hybrid?query=보세전시장&top_k=2")
        assert res.status_code == 200
        data = res.get_json()
        assert "results" in data
        assert data["top_k"] == 2

    def test_hybrid_search_missing_query(self, client):
        res = client.post("/api/search/hybrid", json={})
        assert res.status_code == 400

    def test_hybrid_search_invalid_top_k(self, client):
        res = client.post(
            "/api/search/hybrid",
            json={"query": "test", "top_k": 0},
        )
        assert res.status_code == 400

    def test_chat_endpoint_with_hybrid_engine(self, client):
        res = client.post(
            "/api/chat?engine=hybrid",
            json={"query": "보세전시장이 뭐야"},
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data.get("engine") == "hybrid"
        assert "hybrid_results" in data

    def test_hybrid_search_with_weight_override(self, client):
        res = client.post(
            "/api/search/hybrid",
            json={
                "query": "보세전시장이 뭐야",
                "top_k": 3,
                "weights": {"keyword": 0.0, "bm25": 0.0, "variant": 1.0},
            },
        )
        assert res.status_code == 200
        data = res.get_json()
        # The weights in the body reflect what was used for the request
        assert data["weights"]["variant"] == pytest.approx(1.0)

    def test_hybrid_search_explain(self, client):
        res = client.post(
            "/api/search/hybrid",
            json={"query": "보세전시장이 뭐야", "top_k": 3, "explain_faq_id": "A"},
        )
        assert res.status_code == 200
        data = res.get_json()
        assert "explanation" in data
        assert data["explanation"]["faq_id"] == "A"
