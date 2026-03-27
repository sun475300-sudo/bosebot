"""TF-IDF 유사도 매칭 테스트."""

import pytest
from src.similarity import TFIDFMatcher
from src.utils import load_json


@pytest.fixture
def faq_items():
    faq_data = load_json("data/faq.json")
    return faq_data.get("items", [])


@pytest.fixture
def matcher(faq_items):
    return TFIDFMatcher(faq_items)


class TestTFIDFMatcherInit:
    """TFIDFMatcher 초기화 테스트."""

    def test_init_loads_all_items(self, matcher, faq_items):
        assert len(matcher.faq_items) == len(faq_items)
        assert len(matcher.faq_items) >= 50

    def test_init_builds_tfidf_vectors(self, matcher):
        assert len(matcher.tfidf_vectors) == len(matcher.faq_items)
        assert len(matcher.idf) > 0

    def test_init_documents_match_items(self, matcher):
        assert len(matcher.documents) == len(matcher.faq_items)

    def test_init_with_empty_list(self):
        m = TFIDFMatcher([])
        assert m.faq_items == []
        assert m.tfidf_vectors == []
        assert m.idf == {}


class TestTokenize:
    """토크나이즈 테스트."""

    def test_basic_tokenize(self, matcher):
        tokens = matcher._tokenize("보세전시장이 무엇인가요?")
        assert isinstance(tokens, list)
        assert len(tokens) > 0
        assert "?" not in "".join(tokens)

    def test_empty_string(self, matcher):
        tokens = matcher._tokenize("")
        assert tokens == []

    def test_removes_punctuation(self, matcher):
        tokens = matcher._tokenize("판매, 직매, 현장판매!")
        for t in tokens:
            assert "," not in t
            assert "!" not in t

    def test_lowercases(self, matcher):
        tokens = matcher._tokenize("UNI-PASS 시스템")
        assert all(t == t.lower() for t in tokens)

    def test_single_char_filtered(self, matcher):
        """1글자 토큰은 필터링된다."""
        tokens = matcher._tokenize("가 나 다 보세전시장")
        assert "가" not in tokens
        assert "나" not in tokens


class TestCosineSimilarity:
    """코사인 유사도 테스트."""

    def test_identical_vectors(self, matcher):
        vec = {"a": 1.0, "b": 2.0, "c": 3.0}
        sim = matcher._cosine_similarity(vec, vec)
        assert abs(sim - 1.0) < 0.0001

    def test_orthogonal_vectors(self, matcher):
        vec1 = {"a": 1.0}
        vec2 = {"b": 1.0}
        sim = matcher._cosine_similarity(vec1, vec2)
        assert sim == 0.0

    def test_empty_vectors(self, matcher):
        assert matcher._cosine_similarity({}, {}) == 0.0
        assert matcher._cosine_similarity({"a": 1.0}, {}) == 0.0
        assert matcher._cosine_similarity({}, {"b": 1.0}) == 0.0

    def test_partial_overlap(self, matcher):
        vec1 = {"a": 1.0, "b": 2.0}
        vec2 = {"b": 3.0, "c": 4.0}
        sim = matcher._cosine_similarity(vec1, vec2)
        assert 0.0 < sim < 1.0

    def test_similarity_range(self, matcher):
        """유사도는 0과 1 사이여야 한다."""
        vec1 = {"a": 0.5, "b": 1.5, "c": 0.3}
        vec2 = {"a": 1.2, "b": 0.8, "d": 0.5}
        sim = matcher._cosine_similarity(vec1, vec2)
        assert 0.0 <= sim <= 1.0


class TestFindBestMatch:
    """find_best_match 테스트."""

    def test_general_question(self, matcher):
        results = matcher.find_best_match("보세전시장이 무엇인가요?")
        assert len(results) > 0
        assert results[0]["score"] > 0

    def test_result_structure(self, matcher):
        results = matcher.find_best_match("견본품 반출")
        assert len(results) > 0
        r = results[0]
        assert "item" in r
        assert "score" in r
        assert isinstance(r["item"], dict)
        assert isinstance(r["score"], float)
        assert "id" in r["item"]

    def test_category_filter(self, matcher):
        results = matcher.find_best_match("판매 가능한가요?", category="SALES")
        assert all(r["item"]["category"] == "SALES" for r in results)

    def test_top_k_limit(self, matcher):
        results = matcher.find_best_match("전시 물품", top_k=5)
        assert len(results) <= 5

    def test_top_k_one(self, matcher):
        results = matcher.find_best_match("보세전시장", top_k=1)
        assert len(results) <= 1

    def test_empty_query(self, matcher):
        results = matcher.find_best_match("")
        assert results == []

    def test_unrelated_query_low_score(self, matcher):
        results = matcher.find_best_match("오늘 점심 뭐 먹을까")
        if results:
            assert results[0]["score"] < 0.3

    def test_scores_descending(self, matcher):
        results = matcher.find_best_match("보세전시장 전시 물품 반입", top_k=5)
        for i in range(len(results) - 1):
            assert results[i]["score"] >= results[i + 1]["score"]

    def test_sample_question(self, matcher):
        results = matcher.find_best_match("견본품 수량 제한이 있나요?")
        assert len(results) > 0
        # 견본품 관련 FAQ가 매칭되어야 함
        assert any("견본품" in r["item"].get("question", "") for r in results)

    def test_food_tasting_question(self, matcher):
        results = matcher.find_best_match("시식 행사를 하려면 신고해야 하나요?")
        assert len(results) > 0

    def test_sales_question(self, matcher):
        results = matcher.find_best_match("판매 대금 정산 방법")
        assert len(results) > 0

    def test_no_category_searches_all(self, matcher):
        results_all = matcher.find_best_match("보세전시장", category=None, top_k=10)
        results_filtered = matcher.find_best_match(
            "보세전시장", category="GENERAL", top_k=10
        )
        assert len(results_all) >= len(results_filtered)


class TestChatbotTFIDFFallback:
    """챗봇의 TF-IDF 폴백 통합 테스트."""

    def test_fallback_on_weak_keyword_match(self):
        from src.chatbot import BondedExhibitionChatbot

        chatbot = BondedExhibitionChatbot()
        # 키워드에 직접 매칭되지 않지만 의미적으로 관련된 질문
        result = chatbot.find_matching_faq("물품 전시 기간 중 교체하고 싶습니다", "EXHIBITION")
        assert result is not None

    def test_tfidf_matcher_initialized(self):
        from src.chatbot import BondedExhibitionChatbot

        chatbot = BondedExhibitionChatbot()
        assert chatbot.tfidf_matcher is not None
        assert isinstance(chatbot.tfidf_matcher, TFIDFMatcher)

    def test_faq_count_50(self):
        from src.chatbot import BondedExhibitionChatbot

        chatbot = BondedExhibitionChatbot()
        assert len(chatbot.faq_items) == 50
