"""에스컬레이션 테스트."""

import pytest
from src.escalation import check_escalation, get_escalation_contact


class TestCheckEscalation:
    """check_escalation 함수 테스트."""

    def test_immediate_delivery_triggers(self):
        result = check_escalation("현장에서 즉시 인도 가능한가요?")
        assert result is not None
        assert result["id"] == "ESC001"

    def test_food_tasting_triggers(self):
        result = check_escalation("시식용 식품의 세관장확인은 어떻게 하나요?")
        assert result is not None
        assert result["id"] == "ESC002"

    def test_penalty_triggers(self):
        result = check_escalation("특허 가능성과 제재 가능성이 궁금합니다")
        assert result is not None
        assert result["id"] == "ESC003"

    def test_legal_interpretation_triggers(self):
        result = check_escalation("유권해석을 요청합니다")
        assert result is not None
        assert result["id"] == "ESC004"

    def test_system_issue_triggers(self):
        result = check_escalation("UNI-PASS 시스템 오류가 발생했습니다")
        assert result is not None
        assert result["id"] == "ESC005"

    def test_normal_query_no_escalation(self):
        result = check_escalation("보세전시장이 무엇인가요?")
        assert result is None

    def test_returns_dict_or_none(self):
        result = check_escalation("특허기간은?")
        assert result is None or isinstance(result, dict)


class TestGetEscalationContact:
    """get_escalation_contact 함수 테스트."""

    def test_tech_support_contact(self):
        rule = {"target": "tech_support"}
        contact = get_escalation_contact(rule)
        assert contact["phone"] == "1544-1285"

    def test_customer_support_contact(self):
        rule = {"target": "customer_support"}
        contact = get_escalation_contact(rule)
        assert contact["phone"] == "125"

    def test_unknown_target_falls_back(self):
        rule = {"target": "nonexistent"}
        contact = get_escalation_contact(rule)
        assert "name" in contact
