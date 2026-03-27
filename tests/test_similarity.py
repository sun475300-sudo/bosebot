"""TF-IDF 유사도 매칭 테스트."""

import pytest
from src.similarity import TFIDFMatcher
from src.utils import load_json


@pytest.fixture
def matcher():
    faq_data = load_json("data/faq.json")
    return TFIDFMatcher(faq_data.get("items", []))


class TestTFIDFMatcher:

    def test_init(self, matcher):
        assert len(matcher.faq_items) >= 29
        assert len(matcher.tfidf_vectors) == len(matcher.faq_items)
        assert len(matcher.idf) > 0

    def test_tokenize(self, matcher):
        tokens = matcher._tokenize("보세전시장이 무엇인가요?")
        assert isinstance(tokens, list)
        assert len(tokens) > 0

    def test_find_best_match_general(self, matcher):
        results = matcher.find_best_match("보세전시장이 무엇인가요?")
        assert len(results) > 0
        assert results[0]["score"] > 0

    def test_find_best_match_with_category(self, matcher):
        results = matcher.find_best_match("판매 가능한가요?", category="SALES")
        assert all(r["faq"]["category"] == "SALES" for r in results)

    def test_find_best_match_returns_top_k(self, matcher):
        results = matcher.find_best_match("전시 물품", top_k=5)
        assert len(results) <= 5

    def test_empty_query(self, matcher):
        results = matcher.find_best_match("")
        assert results == []

    def test_unrelated_query(self, matcher):
        results = matcher.find_best_match("오늘 점심 뭐 먹을까")
        # 유사도가 매우 낮거나 빈 결과
        if results:
            assert results[0]["score"] < 0.3

    def test_cosine_similarity_identical(self, matcher):
        vec = {"a": 1.0, "b": 2.0}
        sim = matcher._cosine_similarity(vec, vec)
        assert abs(sim - 1.0) < 0.001

    def test_cosine_similarity_orthogonal(self, matcher):
        vec1 = {"a": 1.0}
        vec2 = {"b": 1.0}
        sim = matcher._cosine_similarity(vec1, vec2)
        assert sim == 0.0

    def test_result_structure(self, matcher):
        results = matcher.find_best_match("견본품 반출")
        if results:
            r = results[0]
            assert "faq" in r
            assert "score" in r
            assert isinstance(r["faq"], dict)
            assert isinstance(r["score"], float)
