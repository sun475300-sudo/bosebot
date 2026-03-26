"""검증기 테스트."""

import pytest
from src.validator import (
    get_needed_confirmations,
    format_confirmation_section,
    CONFIRMATION_QUESTIONS,
)


class TestGetNeededConfirmations:
    """get_needed_confirmations 함수 테스트."""

    def test_always_asks_foreign_goods(self):
        result = get_needed_confirmations("GENERAL", "보세전시장이란?")
        questions = [c["question"] for c in result]
        assert any("외국물품" in q for q in questions)

    def test_sales_asks_purpose_and_plan(self):
        result = get_needed_confirmations("SALES", "판매 가능한가요?")
        questions = [c["question"] for c in result]
        assert any("목적" in q for q in questions)
        assert any("재반출" in q for q in questions)

    def test_food_asks_other_requirements(self):
        result = get_needed_confirmations("FOOD_TASTING", "시식용 식품")
        questions = [c["question"] for c in result]
        assert any("타법 요건" in q for q in questions)

    def test_food_keyword_triggers_requirements(self):
        result = get_needed_confirmations("GENERAL", "식품 관련 문의")
        questions = [c["question"] for c in result]
        assert any("타법 요건" in q for q in questions)

    def test_license_asks_venue(self):
        result = get_needed_confirmations("LICENSE", "특허 신청")
        questions = [c["question"] for c in result]
        assert any("특허" in q for q in questions)

    def test_no_duplicate_questions(self):
        result = get_needed_confirmations("FOOD_TASTING", "시식용 식품 검역")
        questions = [c["question"] for c in result]
        assert len(questions) == len(set(questions))


class TestFormatConfirmationSection:
    """format_confirmation_section 함수 테스트."""

    def test_empty_returns_empty(self):
        result = format_confirmation_section([])
        assert result == ""

    def test_formats_with_header(self):
        items = [{"question": "테스트 질문?", "why": "이유"}]
        result = format_confirmation_section(items)
        assert "민원인이 확인할 사항:" in result
        assert "테스트 질문?" in result

    def test_formats_multiple_items(self):
        items = [
            {"question": "질문1?", "why": "이유1"},
            {"question": "질문2?", "why": "이유2"},
        ]
        result = format_confirmation_section(items)
        assert "질문1?" in result
        assert "질문2?" in result
