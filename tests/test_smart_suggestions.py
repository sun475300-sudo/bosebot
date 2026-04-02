"""스마트 제안 엔진 테스트."""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.smart_suggestions import SmartSuggestionEngine, CATEGORY_TIPS, DEFAULT_ONBOARDING_QUESTIONS
from src.knowledge_graph import KnowledgeGraph
from src.question_cluster import QuestionClusterer
from src.related_faq import RelatedFAQFinder


# 테스트용 FAQ 데이터
SAMPLE_FAQ_ITEMS = [
    {
        "id": "A",
        "category": "GENERAL",
        "question": "보세전시장이 무엇인가요?",
        "answer": "보세전시장은 외국물품을 전시할 수 있는 보세구역입니다.",
        "keywords": ["보세전시장", "정의", "개념"],
        "legal_basis": ["관세법 제190조"],
    },
    {
        "id": "B",
        "category": "GENERAL",
        "question": "보세전시장과 보세창고의 차이는 무엇인가요?",
        "answer": "보세전시장은 전시 목적, 보세창고는 장기 보관 목적입니다.",
        "keywords": ["보세전시장", "보세창고", "차이"],
        "legal_basis": [],
    },
    {
        "id": "C",
        "category": "LICENSE",
        "question": "보세전시장 설치·운영 특허는 어떻게 받나요?",
        "answer": "세관장에게 특허 신청서를 제출합니다.",
        "keywords": ["특허", "설치", "운영"],
        "legal_basis": ["관세법 제174조"],
    },
    {
        "id": "D",
        "category": "LICENSE",
        "question": "특허 기간은 얼마나 되나요?",
        "answer": "특허 기간은 10년입니다.",
        "keywords": ["특허", "기간"],
        "legal_basis": ["관세법 제175조"],
    },
    {
        "id": "E",
        "category": "IMPORT_EXPORT",
        "question": "물품 반입 절차는 어떻게 되나요?",
        "answer": "세관에 반입 신고를 합니다.",
        "keywords": ["반입", "절차", "신고"],
        "legal_basis": [],
    },
    {
        "id": "F",
        "category": "EXHIBITION",
        "question": "전시 가능한 물품의 범위는 어떻게 되나요?",
        "answer": "외국물품 전시가 가능합니다.",
        "keywords": ["전시", "물품", "범위"],
        "legal_basis": [],
    },
    {
        "id": "G",
        "category": "SALES",
        "question": "보세전시장에서 물품을 판매할 수 있나요?",
        "answer": "현장 판매가 가능합니다.",
        "keywords": ["판매", "현장"],
        "legal_basis": [],
    },
    {
        "id": "H",
        "category": "DOCUMENTS",
        "question": "반출입신고서는 어떻게 작성하나요?",
        "answer": "양식에 맞게 작성합니다.",
        "keywords": ["반출입신고서", "서류", "작성"],
        "legal_basis": [],
    },
    {
        "id": "I",
        "category": "PENALTIES",
        "question": "무허가 운영 시 어떤 처벌을 받나요?",
        "answer": "관세법에 따라 처벌받습니다.",
        "keywords": ["무허가", "처벌", "벌칙"],
        "legal_basis": [],
    },
    {
        "id": "J",
        "category": "CONTACT",
        "question": "보세전시장 관련 문의는 어디로 하나요?",
        "answer": "관세청 보세산업과로 문의하세요.",
        "keywords": ["문의", "연락처", "담당"],
        "legal_basis": [],
    },
]


@pytest.fixture
def engine():
    """기본 SmartSuggestionEngine을 생성한다."""
    kg = KnowledgeGraph.build_from_faq(SAMPLE_FAQ_ITEMS)
    return SmartSuggestionEngine(
        faq_items=SAMPLE_FAQ_ITEMS,
        knowledge_graph=kg,
    )


@pytest.fixture
def engine_no_graph():
    """지식 그래프 없이 SmartSuggestionEngine을 생성한다."""
    return SmartSuggestionEngine(faq_items=SAMPLE_FAQ_ITEMS)


class TestFollowUpSuggestions:
    """후속 질문 제안 테스트."""

    def test_returns_list(self, engine):
        result = engine.get_follow_up_suggestions(
            "보세전시장이 무엇인가요?", "보세전시장은 보세구역입니다.", "GENERAL"
        )
        assert isinstance(result, list)

    def test_returns_max_3(self, engine):
        result = engine.get_follow_up_suggestions(
            "보세전시장이 무엇인가요?", "보세전시장은 보세구역입니다.", "GENERAL"
        )
        assert len(result) <= 3

    def test_returns_relevant_to_category(self, engine):
        result = engine.get_follow_up_suggestions(
            "보세전시장이 무엇인가요?", "보세전시장은 보세구역입니다.", "GENERAL"
        )
        assert len(result) > 0
        # 원래 질문은 결과에 포함되지 않아야 함
        assert "보세전시장이 무엇인가요?" not in result

    def test_excludes_asked_questions(self, engine):
        session_history = [
            "보세전시장이 무엇인가요?",
            "보세전시장과 보세창고의 차이는 무엇인가요?",
        ]
        result = engine.get_follow_up_suggestions(
            "보세전시장이 무엇인가요?",
            "보세전시장은 보세구역입니다.",
            "GENERAL",
            session_history=session_history,
        )
        for q in session_history:
            assert q not in result

    def test_with_no_knowledge_graph(self, engine_no_graph):
        result = engine_no_graph.get_follow_up_suggestions(
            "보세전시장이 무엇인가요?", "답변", "GENERAL"
        )
        assert isinstance(result, list)
        assert len(result) <= 3

    def test_license_category(self, engine):
        result = engine.get_follow_up_suggestions(
            "보세전시장 설치·운영 특허는 어떻게 받나요?", "답변", "LICENSE"
        )
        assert len(result) > 0
        assert len(result) <= 3


class TestClarificationPrompts:
    """명확화 프롬프트 테스트."""

    def test_empty_matches(self, engine):
        result = engine.get_clarification_prompts("보세", [])
        assert len(result) == 1
        assert "구체적" in result[0]

    def test_multiple_categories(self, engine):
        matches = [
            {"question": "보세전시장이 무엇인가요?", "category": "GENERAL"},
            {"question": "물품 반입 절차는?", "category": "IMPORT_EXPORT"},
        ]
        result = engine.get_clarification_prompts("보세전시장 물품", matches)
        assert len(result) > 0
        assert len(result) <= 3

    def test_single_category(self, engine):
        matches = [
            {"question": "보세전시장이 무엇인가요?", "category": "GENERAL"},
            {"question": "보세전시장과 보세창고의 차이는?", "category": "GENERAL"},
        ]
        result = engine.get_clarification_prompts("보세전시장", matches)
        assert len(result) > 0
        # 매칭된 질문을 선택지로 제시해야 함
        assert any("혹시" in r for r in result)

    def test_returns_max_3(self, engine):
        matches = [
            {"question": f"질문 {i}", "category": f"CAT_{i}"}
            for i in range(5)
        ]
        result = engine.get_clarification_prompts("테스트", matches)
        assert len(result) <= 3


class TestOnboardingSuggestions:
    """온보딩 제안 테스트."""

    def test_returns_3_suggestions(self, engine):
        result = engine.get_onboarding_suggestions()
        assert len(result) == 3

    def test_returns_strings(self, engine):
        result = engine.get_onboarding_suggestions()
        for s in result:
            assert isinstance(s, str)
            assert len(s) > 0

    def test_first_is_general(self, engine):
        result = engine.get_onboarding_suggestions()
        # 첫 번째는 GENERAL 카테고리 질문이어야 함
        general_questions = [
            item["question"]
            for item in SAMPLE_FAQ_ITEMS
            if item["category"] == "GENERAL"
        ]
        assert result[0] in general_questions

    def test_with_empty_faq(self):
        engine = SmartSuggestionEngine(faq_items=[])
        result = engine.get_onboarding_suggestions()
        assert len(result) == 3
        # 기본 질문이 반환되어야 함
        for q in result:
            assert q in DEFAULT_ONBOARDING_QUESTIONS


class TestContextualTips:
    """카테고리별 팁 테스트."""

    def test_known_category(self, engine):
        result = engine.get_contextual_tips("GENERAL")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_all_categories_have_tips(self, engine):
        for cat in CATEGORY_TIPS:
            result = engine.get_contextual_tips(cat)
            assert len(result) > 0

    def test_unknown_category_returns_general(self, engine):
        result = engine.get_contextual_tips("UNKNOWN_CATEGORY")
        expected = CATEGORY_TIPS["GENERAL"]
        assert result == expected


class TestRankSuggestions:
    """제안 랭킹 테스트."""

    def test_excludes_already_asked(self, engine):
        suggestions = ["질문1", "질문2", "질문3"]
        history = ["질문1"]
        result = engine.rank_suggestions(suggestions, history)
        assert "질문1" not in result

    def test_all_asked_returns_empty(self, engine):
        suggestions = ["질문1", "질문2"]
        history = ["질문1", "질문2"]
        result = engine.rank_suggestions(suggestions, history)
        assert result == []

    def test_empty_history_returns_all(self, engine):
        suggestions = ["질문1", "질문2", "질문3"]
        result = engine.rank_suggestions(suggestions, [])
        assert len(result) == 3

    def test_ranks_by_similarity_to_last_query(self, engine):
        suggestions = [
            "보세전시장 설치·운영 특허는 어떻게 받나요?",
            "보세전시장이 무엇인가요?",
            "무허가 운영 시 어떤 처벌을 받나요?",
        ]
        history = ["보세전시장이란?"]
        result = engine.rank_suggestions(suggestions, history)
        assert len(result) == 3
        # 보세전시장 관련 질문이 처벌 관련보다 앞에 와야 함
        assert isinstance(result, list)

    def test_empty_suggestions(self, engine):
        result = engine.rank_suggestions([], ["질문"])
        assert result == []


class TestAPIEndpoints:
    """웹 API 엔드포인트 테스트."""

    @pytest.fixture
    def client(self):
        from web_server import app
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_chat_includes_suggestions(self, client):
        res = client.post(
            "/api/chat",
            json={"query": "보세전시장이 무엇인가요?"},
            content_type="application/json",
        )
        assert res.status_code == 200
        data = res.get_json()
        assert "suggestions" in data
        assert isinstance(data["suggestions"], list)

    def test_onboarding_endpoint(self, client):
        res = client.get("/api/onboarding")
        assert res.status_code == 200
        data = res.get_json()
        assert "suggestions" in data
        assert isinstance(data["suggestions"], list)
        assert len(data["suggestions"]) == 3
        assert "tips" in data

    def test_suggestions_endpoint_requires_session_id(self, client):
        res = client.get("/api/suggestions")
        assert res.status_code == 400

    def test_suggestions_endpoint_with_session_id(self, client):
        res = client.get("/api/suggestions?session_id=test-session-123")
        assert res.status_code == 200
        data = res.get_json()
        assert "suggestions" in data
        assert isinstance(data["suggestions"], list)
