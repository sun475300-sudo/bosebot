"""에지 케이스 테스트.

복합 키워드, 맞춤법 오류, 긴 질문, 특수문자 등 경계 조건을 테스트한다.
"""

import pytest
from src.chatbot import BondedExhibitionChatbot
from src.classifier import classify_query


@pytest.fixture
def chatbot():
    return BondedExhibitionChatbot()


class TestEdgeCaseQueries:
    """경계 조건 질문 테스트."""

    def test_very_long_query(self, chatbot):
        """매우 긴 질문에도 정상 응답하는지 확인."""
        long_query = "보세전시장에서 " + "외국물품을 전시하고 " * 50 + "판매할 수 있나요?"
        result = chatbot.process_query(long_query)
        assert len(result) > 0
        assert "안내:" in result

    def test_special_characters(self, chatbot):
        """특수문자가 포함된 질문."""
        result = chatbot.process_query("보세전시장이란??? @#$%")
        assert len(result) > 0

    def test_only_spaces(self, chatbot):
        """공백만 있는 질문."""
        result = chatbot.process_query("     ")
        assert "질문을 입력" in result

    def test_single_character(self, chatbot):
        """한 글자 질문."""
        result = chatbot.process_query("?")
        assert len(result) > 0

    def test_mixed_category_query(self, chatbot):
        """여러 카테고리에 걸치는 복합 질문."""
        result = chatbot.process_query(
            "보세전시장에서 시식용 식품을 견본품으로 반출하면서 판매도 가능한가요?"
        )
        assert len(result) > 0
        assert "안내:" in result

    def test_numbers_in_query(self, chatbot):
        """숫자가 포함된 질문."""
        result = chatbot.process_query("관세법 제190조가 무엇인가요?")
        assert len(result) > 0

    def test_english_mixed_query(self, chatbot):
        """영어가 섞인 질문."""
        result = chatbot.process_query("UNI-PASS에서 bonded exhibition 관련 오류")
        assert len(result) > 0

    def test_repeated_query(self, chatbot):
        """같은 질문 반복 시 일관된 응답."""
        result1 = chatbot.process_query("보세전시장이란?")
        result2 = chatbot.process_query("보세전시장이란?")
        assert result1 == result2

    def test_newline_in_query(self, chatbot):
        """개행문자가 포함된 질문."""
        result = chatbot.process_query("보세전시장이\n무엇인가요?")
        assert len(result) > 0


class TestClassifierEdgeCases:
    """분류기 경계 조건 테스트."""

    def test_multi_category_keywords(self):
        """여러 카테고리 키워드가 동시에 포함된 경우."""
        categories = classify_query("판매 견본품 시식 반입 전시")
        assert isinstance(categories, list)
        assert len(categories) >= 1

    def test_partial_keyword_match(self):
        """키워드 부분 일치 확인 (포함 관계)."""
        categories = classify_query("반입신고서를 제출해야 하나요?")
        assert isinstance(categories, list)

    def test_no_keyword_match(self):
        """어떤 키워드도 매칭되지 않는 경우."""
        categories = classify_query("오늘 날씨가 좋습니다")
        assert categories == ["GENERAL"]

    def test_case_sensitivity(self):
        """대소문자 혼합."""
        categories = classify_query("UNI-PASS 오류")
        assert isinstance(categories, list)


class TestNewFAQCoverage:
    """새로 추가된 FAQ 항목 커버리지 테스트."""

    def test_exhibition_category(self, chatbot):
        """EXHIBITION 카테고리 FAQ 매칭."""
        result = chatbot.process_query("보세전시장에서 시연 가능한가요?")
        assert "시연" in result or "전시" in result

    def test_documents_category(self, chatbot):
        """DOCUMENTS 카테고리 FAQ 매칭."""
        result = chatbot.process_query("반출입신고서 양식은 어디서 받나요?")
        assert "신고" in result or "서류" in result

    def test_penalties_category(self, chatbot):
        """PENALTIES 카테고리 FAQ 매칭."""
        result = chatbot.process_query("허가 없이 물품을 반출하면 벌칙이 있나요?")
        assert "벌칙" in result or "처벌" in result or "제재" in result

    def test_contact_category(self, chatbot):
        """CONTACT 카테고리 FAQ 매칭."""
        result = chatbot.process_query("보세전시장 관련 문의는 어디에 하나요?")
        assert "문의" in result or "고객지원" in result or "125" in result

    def test_bonded_warehouse_comparison(self, chatbot):
        """보세창고 비교 질문."""
        result = chatbot.process_query("보세전시장과 보세창고는 어떻게 다른가요?")
        assert "보세창고" in result or "차이" in result

    def test_reexport_question(self, chatbot):
        """재반출 질문."""
        result = chatbot.process_query("전시 끝나고 물품을 해외로 돌려보내려면?")
        assert "반출" in result or "재반출" in result

    def test_remaining_goods_question(self, chatbot):
        """잔류 물품 처리 질문."""
        result = chatbot.process_query("전시 종료 후 남은 물품은 어떻게 하나요?")
        assert "잔류" in result or "처리" in result or "남은" in result

    def test_license_renewal_question(self, chatbot):
        """특허 연장 질문."""
        result = chatbot.process_query("특허 기간을 연장할 수 있나요?")
        assert "연장" in result or "특허" in result
