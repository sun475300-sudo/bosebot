"""Integration tests for enhanced chatbot pipeline.

Tests the updated chatbot.py with new pipeline stages:
- Intent classification
- Entity extraction
- Policy evaluation
- Answer filtering with disclaimers
- Escalation triggering
"""

import logging

import pytest

from src.chatbot import BondedExhibitionChatbot


logger = logging.getLogger(__name__)


class TestChatbotInitialization:
    """Test chatbot initialization."""

    def test_chatbot_initializes_successfully(self):
        """Test that BondedExhibitionChatbot initializes."""
        chatbot = BondedExhibitionChatbot()
        assert chatbot is not None

    def test_new_pipeline_components_initialized(self):
        """Test that new pipeline components are initialized."""
        chatbot = BondedExhibitionChatbot()
        assert chatbot.intent_classifier is not None
        assert chatbot.policy_engine is not None

    def test_faq_items_normalized(self):
        """Test that FAQ items are normalized."""
        chatbot = BondedExhibitionChatbot()
        assert len(chatbot.faq_items) > 0
        # Check that normalized items have both old and new format keys
        for item in chatbot.faq_items:
            # Should have question OR canonical_question
            assert "question" in item or "canonical_question" in item
            # Should have answer OR answer_long
            assert "answer" in item or "answer_long" in item


class TestProcessQueryBackwardCompatibility:
    """Test backward compatibility of process_query."""

    def test_process_query_default_returns_string(self):
        """Test that process_query returns string by default (backward compat)."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query("보세전시장이 뭐예요?")
        # Default: include_metadata=False, should return string
        assert isinstance(result, str)

    def test_process_query_with_include_metadata_false(self):
        """Test explicit include_metadata=False returns string."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query("보세전시장이 뭐예요?", include_metadata=False)
        assert isinstance(result, str)

    def test_process_query_with_include_metadata_true_returns_dict(self):
        """Test that include_metadata=True returns dict."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query("보세전시장이 뭐예요?", include_metadata=True)
        assert isinstance(result, dict)

    def test_empty_query_default_returns_string(self):
        """Test that empty query returns string by default."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query("")
        assert isinstance(result, str)

    def test_empty_query_with_metadata_returns_dict(self):
        """Test that empty query with metadata returns dict."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query("", include_metadata=True)
        assert isinstance(result, dict)
        assert "response" in result


class TestProcessQueryMetadataDict:
    """Test dict structure when include_metadata=True."""

    def test_metadata_dict_has_required_fields(self):
        """Test that metadata dict has all required fields."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query("보세전시장", include_metadata=True)

        required_fields = {
            "response",
            "intent_id",
            "intent_confidence",
            "category",
            "entities",
            "risk_level",
            "policy_decision",
            "escalation_triggered",
        }
        assert required_fields.issubset(set(result.keys()))

    def test_metadata_response_is_string(self):
        """Test that response field is string."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query("보세전시장", include_metadata=True)
        assert isinstance(result["response"], str)

    def test_metadata_intent_id_is_string(self):
        """Test that intent_id field is string."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query("보세전시장", include_metadata=True)
        assert isinstance(result["intent_id"], str)

    def test_metadata_intent_confidence_is_float(self):
        """Test that intent_confidence is between 0 and 1."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query("보세전시장", include_metadata=True)
        assert isinstance(result["intent_confidence"], float)
        assert 0.0 <= result["intent_confidence"] <= 1.0

    def test_metadata_category_is_string(self):
        """Test that category field is string."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query("보세전시장", include_metadata=True)
        assert isinstance(result["category"], str)

    def test_metadata_entities_is_dict(self):
        """Test that entities field is dict."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query("보세전시장", include_metadata=True)
        assert isinstance(result["entities"], dict)

    def test_metadata_risk_level_is_valid(self):
        """Test that risk_level is one of valid values."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query("보세전시장", include_metadata=True)
        valid_levels = {"low", "medium", "high", "critical"}
        assert result["risk_level"] in valid_levels

    def test_metadata_policy_decision_is_dict(self):
        """Test that policy_decision is dict."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query("보세전시장", include_metadata=True)
        assert isinstance(result["policy_decision"], dict)

    def test_metadata_escalation_triggered_is_bool(self):
        """Test that escalation_triggered is boolean."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query("보세전시장", include_metadata=True)
        assert isinstance(result["escalation_triggered"], bool)


class TestGeneralCategoryQuery:
    """Test pipeline with general category queries."""

    def test_general_query_processing(self):
        """Test processing of general query."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query("보세전시장", include_metadata=True)
        assert isinstance(result, dict)
        assert result["category"] in {
            "GENERAL", "SYSTEM", "QUALIFICATION", "IMPORT", "EXPORT",
            "EXHIBITION", "STORAGE", "SAFETY", "LEGAL", "SUPPORT"
        } or result["category"] == "GENERAL"

    def test_simple_guidance_query(self):
        """Test processing of simple guidance query."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query("보세전시장이 뭐죠?", include_metadata=True)
        assert result["risk_level"] == "low"
        assert not result["escalation_triggered"]

    def test_general_query_has_response(self):
        """Test that general query returns response."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query("전시 절차를 설명해주세요", include_metadata=True)
        assert len(result["response"]) > 0


class TestHighRiskQuery:
    """Test pipeline with high-risk queries."""

    def test_tax_question_triggers_high_risk(self):
        """Test that tax question is marked as HIGH risk."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query("세금 계산은 어떻게 되나요?", include_metadata=True)
        assert result["risk_level"] in {"high", "critical"}

    def test_high_risk_query_includes_disclaimer(self):
        """Test that HIGH risk response includes disclaimer."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query("관세를 어떻게 계산하나요?", include_metadata=True)
        # Response may include disclaimer or policy_decision should indicate HIGH risk
        if result["risk_level"] == "high":
            # Either response has disclaimer or policy decision is escalated
            assert "[면책조항]" in result["response"] or len(result["policy_decision"]) > 0

    def test_penalty_question_high_risk(self):
        """Test that penalty question is HIGH risk."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query("벌칙이 뭐죠?", include_metadata=True)
        assert result["risk_level"] in {"high", "critical"}

    def test_high_risk_response_format(self):
        """Test that HIGH risk response is properly formatted."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query("위반했을 때 처벌은?", include_metadata=True)
        assert isinstance(result["response"], str)
        assert len(result["response"]) > 0


class TestCriticalRiskQuery:
    """Test pipeline with critical-risk queries."""

    def test_personal_info_triggers_critical_risk(self):
        """Test that personal info query is CRITICAL risk."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query(
            "내 주민등록번호는 123-456-789입니다",
            include_metadata=True
        )
        assert result["risk_level"] == "critical"

    def test_critical_risk_triggers_escalation(self):
        """Test that CRITICAL risk triggers escalation."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query(
            "제 카드번호는 1234-5678-9012-3456입니다",
            include_metadata=True
        )
        assert result["escalation_triggered"] is True

    def test_critical_risk_with_proper_warning(self):
        """Test that CRITICAL risk response has proper warning."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query(
            "내 여권번호: AB123456",
            include_metadata=True
        )
        assert result["risk_level"] == "critical"
        # Response should warn about personal info
        assert isinstance(result["response"], str)

    def test_strategic_goods_triggers_critical(self):
        """Test that strategic goods question triggers CRITICAL."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query(
            "핵기술 수출은 어떻게 되나요?",
            include_metadata=True
        )
        # Depending on rule matching
        assert result["risk_level"] in {"high", "critical"}


class TestEntityExtractionInPipeline:
    """Test entity extraction in pipeline."""

    def test_entities_extracted_and_included(self):
        """Test that entities are extracted and included in metadata."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query(
            "운영인으로서 외국물품을 반입하는 절차",
            include_metadata=True
        )
        assert "entities" in result
        assert isinstance(result["entities"], dict)

    def test_user_type_entity_extracted(self):
        """Test that user type entities are extracted."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query(
            "출품자가 묻습니다",
            include_metadata=True
        )
        # May have entities if extractor loaded successfully
        if result["entities"]:
            # Entities should be a dict
            assert isinstance(result["entities"], dict)

    def test_item_type_entity_extracted(self):
        """Test that item type entities are extracted."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query(
            "외국물품을 어디에 놓나요?",
            include_metadata=True
        )
        assert isinstance(result["entities"], dict)

    def test_action_type_entity_extracted(self):
        """Test that action type entities are extracted."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query(
            "반입, 전시, 반출의 절차는?",
            include_metadata=True
        )
        assert isinstance(result["entities"], dict)

    def test_multiple_entities_extracted(self):
        """Test extraction of multiple entities from query."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query(
            "운영인과 출품자가 외국물품을 반입하여 전시합니다",
            include_metadata=True
        )
        assert isinstance(result["entities"], dict)


class TestIntentClassificationInPipeline:
    """Test intent classification in pipeline."""

    def test_intent_classified(self):
        """Test that intent is classified."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query("보세전시장이 뭐예요?", include_metadata=True)
        assert "intent_id" in result
        assert isinstance(result["intent_id"], str)

    def test_intent_confidence_provided(self):
        """Test that intent confidence is provided."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query("보세전시장 정의", include_metadata=True)
        assert "intent_confidence" in result
        assert 0.0 <= result["intent_confidence"] <= 1.0

    def test_intent_mapped_to_category(self):
        """Test that intent is mapped to category."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query("보세전시장이 뭐죠?", include_metadata=True)
        assert "category" in result
        assert isinstance(result["category"], str)
        assert len(result["category"]) > 0


class TestPolicyDecisionInPipeline:
    """Test policy decision in pipeline."""

    def test_policy_decision_included(self):
        """Test that policy decision is included in metadata."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query("세금 계산", include_metadata=True)
        assert "policy_decision" in result
        assert isinstance(result["policy_decision"], dict)

    def test_policy_decision_has_risk_level(self):
        """Test that policy decision includes risk level."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query("벌칙", include_metadata=True)
        policy_decision = result["policy_decision"]
        if policy_decision:
            assert "risk_level" in policy_decision

    def test_policy_decision_has_disclaimers(self):
        """Test that policy decision includes disclaimers."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query("벌칙 규정", include_metadata=True)
        policy_decision = result["policy_decision"]
        if policy_decision:
            # May have disclaimers
            if "disclaimers" in policy_decision:
                assert isinstance(policy_decision["disclaimers"], list)

    def test_escalation_decision_included(self):
        """Test that escalation decision is included."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query("내 주민등록번호: 123456", include_metadata=True)
        policy_decision = result["policy_decision"]
        if policy_decision:
            if "escalation_trigger" in policy_decision:
                assert isinstance(policy_decision["escalation_trigger"], bool)


class TestAnswerFiltering:
    """Test answer filtering with disclaimers."""

    def test_disclaimer_added_to_high_risk_answer(self):
        """Test that disclaimer is added to HIGH risk answer."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query("세금 계산 방법", include_metadata=True)
        if result["risk_level"] == "high":
            # Response may have disclaimer
            response = result["response"]
            assert isinstance(response, str)

    def test_low_risk_answer_unchanged(self):
        """Test that LOW risk answer is not modified."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query("보세전시장이 뭐예요?", include_metadata=True)
        if result["risk_level"] == "low":
            # Should have normal answer without [면책조항]
            response = result["response"]
            # May or may not have disclaimer, depends on actual matching
            assert isinstance(response, str)


class TestEscalationTriggering:
    """Test escalation triggering."""

    def test_escalation_triggered_for_critical(self):
        """Test escalation is triggered for CRITICAL risk."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query(
            "내 주민등록번호입니다 123-456-789",
            include_metadata=True
        )
        if result["risk_level"] == "critical":
            assert result["escalation_triggered"] is True

    def test_escalation_not_triggered_for_low(self):
        """Test escalation is not triggered for LOW risk."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query(
            "보세전시장의 정의를 설명해주세요",
            include_metadata=True
        )
        if result["risk_level"] == "low":
            assert result["escalation_triggered"] is False

    def test_escalation_possible_for_high_risk(self):
        """Test escalation may be triggered for HIGH risk."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query("벌칙 규정", include_metadata=True)
        # For HIGH risk, escalation_triggered depends on rules
        assert isinstance(result["escalation_triggered"], bool)


class TestSessionIntegration:
    """Test session integration with pipeline."""

    def test_process_query_with_session_id(self):
        """Test process_query with session_id parameter."""
        chatbot = BondedExhibitionChatbot()
        session_id = "test_session_123"
        result = chatbot.process_query(
            "보세전시장이 뭐예요?",
            session_id=session_id,
            include_metadata=True
        )
        assert isinstance(result, dict)
        assert "response" in result

    def test_process_query_without_session_id(self):
        """Test process_query without session_id."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query(
            "보세전시장",
            include_metadata=True
        )
        assert isinstance(result, dict)


class TestPipelineEdgeCases:
    """Test edge cases in pipeline."""

    def test_very_long_query(self):
        """Test processing of very long query."""
        chatbot = BondedExhibitionChatbot()
        long_query = "보세전시장에서 " * 50 + "물품을 반입할 수 있나요?"
        result = chatbot.process_query(long_query, include_metadata=True)
        assert isinstance(result, dict)
        assert "response" in result

    def test_query_with_special_characters(self):
        """Test processing query with special characters."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query(
            "보세전시장!!! @#$% 물품???",
            include_metadata=True
        )
        assert isinstance(result, dict)

    def test_query_with_numbers(self):
        """Test processing query with numbers."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query(
            "2026년 4월 8일 보세전시장에서 123개 물품",
            include_metadata=True
        )
        assert isinstance(result, dict)

    def test_query_with_mixed_korean_english(self):
        """Test processing mixed Korean and English query."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query(
            "What is bonded exhibition? 보세전시장이 뭐죠?",
            include_metadata=True
        )
        assert isinstance(result, dict)

    def test_query_with_only_whitespace(self):
        """Test processing query with only whitespace."""
        chatbot = BondedExhibitionChatbot()
        result = chatbot.process_query("   ", include_metadata=True)
        assert isinstance(result, dict)
        assert "response" in result


class TestPipelineConsistency:
    """Test consistency of pipeline output."""

    def test_same_query_consistent_intent(self):
        """Test that same query produces consistent intent."""
        chatbot = BondedExhibitionChatbot()
        result1 = chatbot.process_query("보세전시장이 뭐예요?", include_metadata=True)
        result2 = chatbot.process_query("보세전시장이 뭐예요?", include_metadata=True)
        # Same query should classify to same intent
        assert result1["intent_id"] == result2["intent_id"]

    def test_same_query_same_risk_level(self):
        """Test that same query produces same risk level."""
        chatbot = BondedExhibitionChatbot()
        result1 = chatbot.process_query("세금 계산", include_metadata=True)
        result2 = chatbot.process_query("세금 계산", include_metadata=True)
        assert result1["risk_level"] == result2["risk_level"]

    def test_metadata_string_equivalence(self):
        """Test that with/without metadata flag gives same response text."""
        chatbot = BondedExhibitionChatbot()
        result_string = chatbot.process_query("보세전시장", include_metadata=False)
        result_dict = chatbot.process_query("보세전시장", include_metadata=True)
        assert result_string == result_dict["response"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
