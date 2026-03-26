"""분류기 테스트."""

import pytest
from src.classifier import classify_query, get_primary_category


class TestClassifyQuery:
    """classify_query 함수 테스트."""

    def test_general_question(self):
        result = classify_query("보세전시장이 무엇인가요?")
        assert "GENERAL" in result

    def test_import_export_question(self):
        result = classify_query("물품을 반입하려면 신고가 필요한가요?")
        assert "IMPORT_EXPORT" in result

    def test_sales_question(self):
        result = classify_query("전시한 물품을 현장에서 바로 판매할 수 있나요?")
        assert "SALES" in result

    def test_sales_display_question(self):
        result = classify_query("현장에서 판매 가능한가요?")
        assert "SALES" in result

    def test_sample_question(self):
        result = classify_query("견본품으로 밖에 가져가도 되나요?")
        assert "SAMPLE" in result

    def test_food_tasting_question(self):
        result = classify_query("시식용 식품을 들여오는 경우 요건확인은?")
        assert "FOOD_TASTING" in result

    def test_license_question(self):
        result = classify_query("보세전시장 특허기간은 어떻게 되나요?")
        categories = classify_query("보세전시장 특허기간은 어떻게 되나요?")
        assert "LICENSE" in categories or "GENERAL" in categories

    def test_penalty_question(self):
        result = classify_query("위반하면 벌칙이 있나요?")
        assert "PENALTIES" in result

    def test_contact_question(self):
        result = classify_query("어디에 문의하면 되나요?")
        assert "CONTACT" in result

    def test_documents_question(self):
        result = classify_query("신고서 양식은 어디서 받나요?")
        assert "DOCUMENTS" in result

    def test_empty_query_returns_general(self):
        result = classify_query("안녕하세요")
        assert result == ["GENERAL"]

    def test_returns_list(self):
        result = classify_query("보세전시장이란?")
        assert isinstance(result, list)
        assert len(result) >= 1


class TestGetPrimaryCategory:
    """get_primary_category 함수 테스트."""

    def test_returns_string(self):
        result = get_primary_category("보세전시장이란?")
        assert isinstance(result, str)

    def test_general_primary(self):
        result = get_primary_category("안녕하세요")
        assert result == "GENERAL"
