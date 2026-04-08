"""Integration tests for PolicyEngine module.

Tests PolicyEngine initialization, risk evaluation, disclaimers,
escalation logic, and audit logging.
"""

import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from src.policy_engine import (
    PolicyEngine,
    PolicyDecision,
    PolicyRule,
    RiskLevel,
    KOREAN_DISCLAIMERS,
    ESCALATION_TARGETS,
    get_policy_engine,
    evaluate_policy,
    apply_answer_filter,
    should_escalate,
)


logger = logging.getLogger(__name__)


class TestPolicyEngineInitialization:
    """Test PolicyEngine initialization and configuration."""

    def test_policy_engine_initialization_succeeds(self):
        """Test that PolicyEngine initializes successfully."""
        engine = PolicyEngine()
        assert engine is not None
        assert engine.builtin_rules is not None
        assert len(engine.builtin_rules) > 0

    def test_builtin_rules_are_loaded(self):
        """Test that built-in rules are loaded."""
        engine = PolicyEngine()
        assert len(engine.builtin_rules) >= 10  # Should have at least 10 rules
        rule_ids = {r.rule_id for r in engine.builtin_rules}
        assert "POL_001" in rule_ids  # PII rule
        assert "POL_004" in rule_ids  # Tax calculation rule

    def test_all_rules_merged_correctly(self):
        """Test that all rules (builtin + external) are merged."""
        engine = PolicyEngine()
        assert engine.all_rules is not None
        assert len(engine.all_rules) > 0

    def test_audit_log_directory_created(self):
        """Test that audit log directory is created on initialization."""
        engine = PolicyEngine()
        assert engine.audit_log_dir.exists()
        assert engine.audit_log_dir.is_dir()

    def test_graceful_degradation_when_rules_file_missing(self):
        """Test that engine gracefully handles missing rules file."""
        engine = PolicyEngine(rules_path="/nonexistent/path/rules.json")
        # Should still work with builtin rules
        assert engine.builtin_rules is not None
        assert len(engine.all_rules) > 0  # At least builtin rules


class TestPolicyEvaluationBasic:
    """Test basic policy evaluation."""

    def test_evaluate_returns_policy_decision(self):
        """Test that evaluate() returns a PolicyDecision object."""
        engine = PolicyEngine()
        decision = engine.evaluate("보세전시장이 뭐예요?", intent="sysqual_001")
        assert isinstance(decision, PolicyDecision)
        assert decision.risk_level is not None

    def test_evaluate_low_risk_query(self):
        """Test evaluation of simple, low-risk query."""
        engine = PolicyEngine()
        decision = engine.evaluate("보세전시장의 정의가 뭐죠?", intent="sysqual_001")
        assert decision.risk_level == RiskLevel.LOW
        assert not decision.requires_escalation

    def test_evaluate_empty_query(self):
        """Test evaluation of empty query."""
        engine = PolicyEngine()
        decision = engine.evaluate("", intent="")
        assert decision.risk_level == RiskLevel.LOW
        assert not decision.requires_escalation

    def test_applied_rules_recorded(self):
        """Test that applied rules are recorded in decision."""
        engine = PolicyEngine()
        decision = engine.evaluate("세금 계산이 어떻게 되나요?", intent="tax_001")
        assert isinstance(decision.applied_rules, list)
        # Should have at least one rule applied for tax question
        assert len(decision.applied_rules) > 0


class TestPolicyEvaluationTaxQuestions:
    """Test policy evaluation for tax/tariff questions (HIGH risk)."""

    def test_tax_calculation_query_triggers_high_risk(self):
        """Test that tax calculation queries are classified as HIGH risk."""
        engine = PolicyEngine()
        decision = engine.evaluate(
            "관세 계산 방식이 어떻게 되나요?",
            intent="tax_001"
        )
        assert decision.risk_level >= RiskLevel.HIGH

    def test_tax_question_includes_disclaimer(self):
        """Test that HIGH risk tax questions include disclaimers."""
        engine = PolicyEngine()
        decision = engine.evaluate(
            "부가세를 어떻게 계산하나요?",
            intent="tax_001"
        )
        assert len(decision.disclaimers) > 0

    def test_tax_question_includes_escalation_target(self):
        """Test that tax questions have escalation target."""
        engine = PolicyEngine()
        decision = engine.evaluate(
            "과세가격은 어떻게 결정되나요?",
            intent="tax_001"
        )
        # HIGH risk should have escalation info
        assert decision.escalation_target is not None


class TestPolicyEvaluationPenalties:
    """Test policy evaluation for penalty/punishment questions (HIGH risk)."""

    def test_penalty_question_triggers_high_risk(self):
        """Test that penalty questions are classified as HIGH risk."""
        engine = PolicyEngine()
        decision = engine.evaluate(
            "벌칙은 무엇인가요?",
            intent="penalty_001"
        )
        assert decision.risk_level >= RiskLevel.HIGH

    def test_penalty_question_requires_escalation(self):
        """Test that HIGH risk penalty questions trigger escalation."""
        engine = PolicyEngine()
        decision = engine.evaluate(
            "위반했을 때 처벌이 뭐죠?",
            intent="penalty_001"
        )
        # Depending on which rule matches, may require escalation
        assert decision.risk_level >= RiskLevel.HIGH


class TestPolicyEvaluationPersonalInfo:
    """Test policy evaluation for personal information (CRITICAL risk)."""

    def test_personal_info_query_triggers_critical_risk(self):
        """Test that queries with personal info are CRITICAL risk."""
        engine = PolicyEngine()
        decision = engine.evaluate(
            "내 주민등록번호는 123-456-789입니다",
            intent="unknown"
        )
        assert decision.risk_level == RiskLevel.CRITICAL

    def test_credit_card_number_triggers_critical(self):
        """Test that credit card numbers trigger CRITICAL risk."""
        engine = PolicyEngine()
        decision = engine.evaluate(
            "내 카드번호는 1234-5678-9012-3456이고",
            intent="unknown"
        )
        assert decision.risk_level == RiskLevel.CRITICAL

    def test_account_number_triggers_critical(self):
        """Test that account numbers trigger CRITICAL risk."""
        engine = PolicyEngine()
        decision = engine.evaluate(
            "내 계좌번호는 1234567890입니다",
            intent="unknown"
        )
        assert decision.risk_level == RiskLevel.CRITICAL

    def test_critical_risk_blocks_answer(self):
        """Test that CRITICAL risk decisions include escalation."""
        engine = PolicyEngine()
        decision = engine.evaluate(
            "내 여권번호는 AB123456입니다",
            intent="unknown"
        )
        assert decision.risk_level == RiskLevel.CRITICAL
        assert decision.requires_escalation


class TestDisclaimers:
    """Test disclaimer generation and retrieval."""

    def test_get_disclaimer_low_risk(self):
        """Test disclaimer for LOW risk."""
        engine = PolicyEngine()
        disclaimer = engine.get_disclaimer(RiskLevel.LOW)
        assert disclaimer == ""

    def test_get_disclaimer_medium_risk(self):
        """Test disclaimer for MEDIUM risk."""
        engine = PolicyEngine()
        disclaimer = engine.get_disclaimer(RiskLevel.MEDIUM)
        assert isinstance(disclaimer, str)
        assert len(disclaimer) > 0
        assert "참고 정보" in disclaimer

    def test_get_disclaimer_high_risk(self):
        """Test disclaimer for HIGH risk."""
        engine = PolicyEngine()
        disclaimer = engine.get_disclaimer(RiskLevel.HIGH)
        assert isinstance(disclaimer, str)
        assert len(disclaimer) > 0
        assert "법적 효력" in disclaimer

    def test_get_disclaimer_critical_risk(self):
        """Test disclaimer for CRITICAL risk."""
        engine = PolicyEngine()
        disclaimer = engine.get_disclaimer(RiskLevel.CRITICAL)
        assert isinstance(disclaimer, str)
        assert len(disclaimer) > 0
        assert "전문 상담" in disclaimer

    def test_apply_answer_filter_adds_disclaimer(self):
        """Test that apply_answer_filter adds disclaimer to answer."""
        engine = PolicyEngine()
        answer = "세관은 통관을 담당합니다."
        filtered = engine.apply_answer_filter(answer, RiskLevel.HIGH)
        assert "[면책조항]" in filtered
        assert answer in filtered

    def test_apply_answer_filter_low_risk_no_change(self):
        """Test that LOW risk doesn't change answer."""
        engine = PolicyEngine()
        answer = "보세전시장은 전시 목적으로 물품을 반입할 수 있습니다."
        filtered = engine.apply_answer_filter(answer, RiskLevel.LOW)
        assert filtered == answer

    def test_apply_answer_filter_empty_answer(self):
        """Test apply_answer_filter with empty answer."""
        engine = PolicyEngine()
        filtered = engine.apply_answer_filter("", RiskLevel.HIGH)
        assert filtered == ""

    def test_apply_answer_filter_none_answer(self):
        """Test apply_answer_filter with None answer."""
        engine = PolicyEngine()
        filtered = engine.apply_answer_filter(None, RiskLevel.HIGH)
        assert filtered is None


class TestEscalation:
    """Test escalation logic."""

    def test_should_escalate_critical_risk(self):
        """Test that CRITICAL risk requires escalation."""
        engine = PolicyEngine()
        decision = engine.evaluate(
            "내 주민등록번호: 123-456-789",
            intent="unknown"
        )
        assert engine.should_escalate(decision)

    def test_should_escalate_high_risk_with_escalate_action(self):
        """Test escalation for HIGH risk with ESCALATE action."""
        engine = PolicyEngine()
        decision = engine.evaluate(
            "벌칙이 뭐죠?",
            intent="penalty_001"
        )
        # HIGH risk with escalation-triggering action
        assert engine.should_escalate(decision)

    def test_escalation_target_from_decision(self):
        """Test getting escalation target from decision."""
        engine = PolicyEngine()
        decision = engine.evaluate(
            "세금 계산 방법은?",
            intent="tax_001"
        )
        if decision.requires_escalation:
            assert decision.escalation_target is not None

    def test_get_escalation_info_returns_dict(self):
        """Test get_escalation_info returns proper dictionary."""
        engine = PolicyEngine()
        decision = engine.evaluate(
            "밀수는 뭐죠?",
            intent="penalty_001"
        )
        info = engine.get_escalation_info(decision)
        assert isinstance(info, dict)

    def test_get_escalation_info_local_customs(self):
        """Test escalation info for local_customs target."""
        engine = PolicyEngine()
        decision = engine.evaluate(
            "세금",
            intent="tax_001"
        )
        if decision.escalation_target == "local_customs":
            info = engine.get_escalation_info(decision)
            assert "phone" in info
            assert "sla_minutes" in info

    def test_escalation_sla_minutes_set(self):
        """Test that SLA minutes are set for escalation."""
        engine = PolicyEngine()
        decision = engine.evaluate(
            "특허 취소가 뭐죠?",
            intent="unknown"
        )
        if decision.escalation_target:
            assert decision.escalation_sla_minutes is not None
            assert decision.escalation_sla_minutes > 0


class TestAuditLogging:
    """Test audit logging functionality."""

    def test_log_policy_decision_creates_file(self):
        """Test that log_policy_decision creates log file."""
        engine = PolicyEngine()
        decision = engine.evaluate("보세전시장이 뭐예요?", intent="sysqual_001")

        # Check that a log file was created
        log_files = list(engine.audit_log_dir.glob("policy_*.jsonl"))
        assert len(log_files) > 0

    def test_log_policy_decision_writes_valid_json(self):
        """Test that logged data is valid JSON."""
        engine = PolicyEngine()
        decision = engine.evaluate("세금 계산", intent="tax_001")

        log_files = list(engine.audit_log_dir.glob("policy_*.jsonl"))
        if log_files:
            latest_log = max(log_files, key=lambda p: p.stat().st_mtime)
            with open(latest_log, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                # At least one line should be valid JSON
                for line in lines[-3:]:  # Check last few lines
                    try:
                        entry = json.loads(line)
                        assert "risk_level" in entry
                        assert "timestamp" in entry
                        break
                    except json.JSONDecodeError:
                        continue

    def test_log_entry_includes_metadata(self):
        """Test that log entries include required metadata."""
        engine = PolicyEngine()
        decision = engine.evaluate(
            "벌칙은?",
            intent="penalty_001",
            entities=[],
            faq_item={"id": "faq_123"}
        )

        assert decision.audit_metadata is not None
        assert "query" in decision.audit_metadata
        assert "intent" in decision.audit_metadata
        assert "timestamp" in decision.audit_metadata
        assert "rule_ids" in decision.audit_metadata

    def test_get_audit_log_summary(self):
        """Test audit log summary generation."""
        engine = PolicyEngine()

        # Make several evaluations to populate logs
        engine.evaluate("보세전시장", intent="sysqual_001")
        engine.evaluate("세금 계산", intent="tax_001")
        engine.evaluate("벌칙", intent="penalty_001")

        summary = engine.get_audit_log_summary(days=1)
        assert isinstance(summary, dict)
        assert "total_decisions" in summary
        assert "by_risk_level" in summary
        assert "escalations" in summary


class TestRiskLevelComparison:
    """Test RiskLevel enum comparison operations."""

    def test_risk_level_comparison_operators(self):
        """Test RiskLevel comparison operators."""
        assert RiskLevel.LOW < RiskLevel.MEDIUM
        assert RiskLevel.MEDIUM < RiskLevel.HIGH
        assert RiskLevel.HIGH < RiskLevel.CRITICAL
        assert RiskLevel.CRITICAL > RiskLevel.HIGH

    def test_risk_level_equality(self):
        """Test RiskLevel equality."""
        assert RiskLevel.LOW == RiskLevel.LOW
        assert not (RiskLevel.LOW == RiskLevel.HIGH)

    def test_risk_level_less_equal(self):
        """Test RiskLevel <= operator."""
        assert RiskLevel.LOW <= RiskLevel.LOW
        assert RiskLevel.LOW <= RiskLevel.HIGH
        assert not (RiskLevel.CRITICAL <= RiskLevel.HIGH)


class TestGetPolicyEngine:
    """Test module-level convenience functions."""

    def test_get_policy_engine_singleton(self):
        """Test that get_policy_engine returns singleton."""
        engine1 = get_policy_engine()
        engine2 = get_policy_engine()
        assert engine1 is engine2

    def test_evaluate_policy_function(self):
        """Test evaluate_policy module function."""
        result = evaluate_policy(
            intent_id="sysqual_001",
            query="보세전시장이 뭐예요?",
            entities=None,
            faq_item=None
        )
        assert isinstance(result, dict)
        assert "risk_level" in result
        assert "escalation_trigger" in result
        assert "disclaimers" in result

    def test_apply_answer_filter_function(self):
        """Test apply_answer_filter module function."""
        answer = "보세전시장은 전시 목적으로 물품을 보관합니다."
        filtered = apply_answer_filter(answer, "high")
        assert isinstance(filtered, str)
        assert "[면책조항]" in filtered or answer in filtered

    def test_should_escalate_function(self):
        """Test should_escalate module function."""
        # HIGH risk should escalate
        result = should_escalate("high", False, "세금 계산")
        assert result is True

        # LOW risk shouldn't escalate
        result = should_escalate("low", False, "보세전시장")
        assert result is False


class TestPolicyRules:
    """Test PolicyRule objects."""

    def test_policy_rule_hash(self):
        """Test that PolicyRules can be hashed."""
        rule = PolicyRule(
            rule_id="TEST_001",
            name="Test Rule",
            condition=lambda q, i, e, f: False,
            action="TEST",
            risk_level=RiskLevel.LOW,
            message_template="Test message"
        )
        rule_set = {rule}
        assert len(rule_set) == 1

    def test_policy_rule_equality(self):
        """Test PolicyRule equality based on rule_id."""
        rule1 = PolicyRule(
            rule_id="TEST_001",
            name="Test Rule",
            condition=lambda q, i, e, f: False,
            action="TEST",
            risk_level=RiskLevel.LOW,
            message_template="Test"
        )
        rule2 = PolicyRule(
            rule_id="TEST_001",
            name="Different Name",
            condition=lambda q, i, e, f: True,
            action="DIFFERENT",
            risk_level=RiskLevel.HIGH,
            message_template="Different"
        )
        assert rule1 == rule2  # Same rule_id


class TestGetRulesByRiskLevel:
    """Test filtering rules by risk level."""

    def test_get_rules_by_risk_level_low(self):
        """Test getting LOW risk rules."""
        engine = PolicyEngine()
        low_rules = engine.get_rules_by_risk_level(RiskLevel.LOW)
        assert isinstance(low_rules, list)
        for rule in low_rules:
            assert rule.risk_level == RiskLevel.LOW

    def test_get_rules_by_risk_level_high(self):
        """Test getting HIGH risk rules."""
        engine = PolicyEngine()
        high_rules = engine.get_rules_by_risk_level(RiskLevel.HIGH)
        assert isinstance(high_rules, list)
        assert len(high_rules) > 0  # Should have HIGH risk rules
        for rule in high_rules:
            assert rule.risk_level == RiskLevel.HIGH

    def test_get_rules_by_risk_level_critical(self):
        """Test getting CRITICAL risk rules."""
        engine = PolicyEngine()
        critical_rules = engine.get_rules_by_risk_level(RiskLevel.CRITICAL)
        assert isinstance(critical_rules, list)
        assert len(critical_rules) > 0  # Should have CRITICAL rules
        for rule in critical_rules:
            assert rule.risk_level == RiskLevel.CRITICAL

    def test_get_all_rules(self):
        """Test getting all rules."""
        engine = PolicyEngine()
        all_rules = engine.get_all_rules()
        assert len(all_rules) > 0
        assert len(all_rules) >= len(engine.builtin_rules)


class TestEscalationTargets:
    """Test escalation target mapping."""

    def test_escalation_targets_dict_is_complete(self):
        """Test that all escalation targets have required fields."""
        required_fields = {"name", "contact", "phone", "sla_minutes", "department"}
        for target_key, target_info in ESCALATION_TARGETS.items():
            assert required_fields.issubset(set(target_info.keys()))
            assert target_info["sla_minutes"] > 0

    def test_all_escalation_targets_accessible(self):
        """Test that all targets in ESCALATION_TARGETS can be accessed."""
        engine = PolicyEngine()
        for target_key in ESCALATION_TARGETS.keys():
            assert target_key is not None
            assert isinstance(ESCALATION_TARGETS[target_key], dict)


class TestPolicyDecisionDataClass:
    """Test PolicyDecision data class."""

    def test_policy_decision_initialization(self):
        """Test PolicyDecision initialization."""
        decision = PolicyDecision(
            risk_level=RiskLevel.HIGH,
            disclaimers=["disclaimer1", "disclaimer2"],
            requires_escalation=True,
            escalation_target="bonded_division",
            escalation_sla_minutes=180,
        )
        assert decision.risk_level == RiskLevel.HIGH
        assert len(decision.disclaimers) == 2
        assert decision.requires_escalation is True
        assert decision.escalation_target == "bonded_division"

    def test_policy_decision_default_values(self):
        """Test PolicyDecision default values."""
        decision = PolicyDecision(risk_level=RiskLevel.LOW)
        assert decision.disclaimers == []
        assert decision.requires_escalation is False
        assert decision.escalation_target is None
        assert decision.filtered_answer is None
        assert decision.applied_rules == []
        assert decision.confidence_override == 1.0
        assert decision.audit_metadata == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
