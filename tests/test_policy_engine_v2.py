"""Tests for Policy Engine v2 (risk-based answer control).

Covers:
- Risk level detection per category (legal / tax / sensitive / food).
- Multi-agency routing (FOOD_TASTING -> 식약처).
- Sensitive keyword detection (critical).
- Disclaimer generation.
- Admin API endpoints with ADMIN_AUTH_DISABLED=true.
"""

from __future__ import annotations

import os
import sys

import pytest

# Ensure the repo root is on sys.path so ``from src...`` works when this
# module is invoked directly.
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

from src.policy_engine_v2 import (
    DISCLAIMERS,
    ESCALATION_DIRECTORY,
    PolicyEngineV2,
    evaluate_query,
    get_policy_engine_v2,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def engine() -> PolicyEngineV2:
    return PolicyEngineV2()


@pytest.fixture
def api_client():
    """Flask test client with admin auth disabled."""
    os.environ["ADMIN_AUTH_DISABLED"] = "true"
    os.environ["TESTING"] = "true"
    from web_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c
    os.environ.pop("ADMIN_AUTH_DISABLED", None)
    os.environ.pop("TESTING", None)


# ---------------------------------------------------------------------------
# Structure / contract
# ---------------------------------------------------------------------------


class TestDecisionShape:
    def test_decision_contains_required_keys(self, engine):
        d = engine.evaluate("보세전시장이 뭐예요?")
        for key in (
            "risk_level",
            "answer_policy",
            "restrictions",
            "required_disclaimers",
            "escalation_required",
            "escalation_target",
            "confidence",
        ):
            assert key in d, f"missing key: {key}"

    def test_risk_level_values_are_valid(self, engine):
        d = engine.evaluate("hi")
        assert d["risk_level"] in {"low", "medium", "high", "critical"}

    def test_answer_policy_values_are_valid(self, engine):
        d = engine.evaluate("hi")
        assert d["answer_policy"] in {
            "direct",
            "conditional",
            "restricted",
            "escalation_only",
        }


# ---------------------------------------------------------------------------
# Risk level detection
# ---------------------------------------------------------------------------


class TestLegalJudgmentDetection:
    def test_possibility_question_is_high(self, engine):
        d = engine.evaluate("이거 반출 가능한가요?")
        assert d["risk_level"] in {"high", "critical"}
        assert "no_definitive_judgment" in d["restrictions"]

    def test_illegality_question_is_high(self, engine):
        d = engine.evaluate("이 행위는 위법인가요?")
        assert d["risk_level"] in {"high", "critical"}

    def test_do_possible_phrase_is_high(self, engine):
        d = engine.evaluate("이렇게 해도 되나요?")
        assert d["risk_level"] in {"high", "critical"}

    def test_simple_info_is_low(self, engine):
        d = engine.evaluate("보세전시장 운영 시간이 궁금합니다")
        assert d["risk_level"] == "low"
        assert d["answer_policy"] == "direct"


class TestTaxDetermination:
    def test_tax_keyword_is_high(self, engine):
        d = engine.evaluate("관세율은 얼마인가요?")
        assert d["risk_level"] == "high"
        assert "requires_agency_verification" in d["restrictions"]

    def test_exemption_keyword_is_high(self, engine):
        d = engine.evaluate("이 상품은 면세 대상인가요?")
        assert d["risk_level"] in {"high", "critical"}

    def test_taxation_keyword_is_high(self, engine):
        d = engine.evaluate("과세 기준이 어떻게 되나요?")
        # tax keyword alone is high; the "되나요" phrase may promote, that's fine
        assert d["risk_level"] in {"high", "critical"}


class TestSensitiveKeywords:
    def test_smuggling_is_critical(self, engine):
        d = engine.evaluate("밀수하면 어떻게 되나요?")
        assert d["risk_level"] == "critical"
        assert d["answer_policy"] == "escalation_only"
        assert d["escalation_required"] is True

    def test_tax_evasion_is_critical(self, engine):
        d = engine.evaluate("탈세 방법 알려주세요")
        assert d["risk_level"] == "critical"

    def test_false_declaration_is_critical(self, engine):
        d = engine.evaluate("허위 신고로 처리하면 어떻게 되나요?")
        assert d["risk_level"] == "critical"


class TestMultiAgencyRouting:
    def test_food_tasting_routes_to_food_safety(self, engine):
        d = engine.evaluate(
            "시식 행사 식품 잔량은 어떻게 처리하나요?",
            category="FOOD_TASTING",
        )
        assert d["escalation_target"] == "식약처"
        assert "requires_agency_verification" in d["restrictions"]

    def test_food_tasting_without_food_keyword_still_routes(self, engine):
        d = engine.evaluate("행사가 어떻게 진행되나요?", category="FOOD_TASTING")
        assert d["escalation_target"] == "식약처"

    def test_explicit_fda_mention_routes_to_fda(self, engine):
        d = engine.evaluate("식약처에 확인해야 하나요?")
        assert d["escalation_target"] == "식약처"

    def test_drug_mention_routes_to_fda(self, engine):
        d = engine.evaluate("의약품 반입 절차")
        assert d["escalation_target"] == "식약처"


# ---------------------------------------------------------------------------
# Disclaimer / escalation info helpers
# ---------------------------------------------------------------------------


class TestDisclaimerGeneration:
    def test_get_disclaimer_for_each_level(self, engine):
        for level in ("low", "medium", "high", "critical"):
            assert engine.get_disclaimer(level) == DISCLAIMERS[level]

    def test_unknown_level_falls_back_to_low(self, engine):
        assert engine.get_disclaimer("unknown") == DISCLAIMERS["low"]

    def test_disclaimer_is_included_in_decision(self, engine):
        d = engine.evaluate("관세율은 얼마인가요?")
        assert any(s in d["required_disclaimers"] for s in DISCLAIMERS.values())
        # Agency-verification requires the "관할 세관 확인 필요" disclaimer.
        assert DISCLAIMERS["medium"] in d["required_disclaimers"]

    def test_agency_verification_triggers_korean_disclaimer(self, engine):
        d = engine.evaluate("면세 기준이 궁금합니다")
        assert "개별 사안은 관할 세관 확인 필요" in d["required_disclaimers"]


class TestEscalationInfo:
    def test_get_escalation_info_for_customs(self, engine):
        info = engine.get_escalation_info("관할 세관")
        assert info and info["phone"]

    def test_get_escalation_info_for_food_safety(self, engine):
        info = engine.get_escalation_info("식약처")
        assert info["phone"] == "1577-1255"

    def test_get_escalation_info_unknown(self, engine):
        assert engine.get_escalation_info("없는대상") == {}

    def test_get_escalation_info_none(self, engine):
        assert engine.get_escalation_info(None) == {}


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


class TestModuleHelpers:
    def test_singleton_returns_same_instance(self):
        a = get_policy_engine_v2()
        b = get_policy_engine_v2()
        assert a is b

    def test_evaluate_query_shortcut(self):
        d = evaluate_query("밀수하면 어떻게 되나요?")
        assert d["risk_level"] == "critical"

    def test_non_string_query_handled(self, engine):
        d = engine.evaluate(None)  # type: ignore[arg-type]
        assert d["risk_level"] == "low"

    def test_rules_dump_has_expected_keys(self, engine):
        rules = engine.get_rules()
        assert rules["version"].startswith("2.")
        assert "disclaimers" in rules
        assert "escalation_directory" in rules
        assert set(ESCALATION_DIRECTORY).issubset(rules["escalation_directory"])


# ---------------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------------


class TestAdminAPI:
    def test_evaluate_endpoint_returns_decision(self, api_client):
        res = api_client.post(
            "/api/admin/policy/evaluate",
            json={"query": "밀수하면 어떻게 되나요?"},
        )
        assert res.status_code == 200
        body = res.get_json()
        assert body["risk_level"] == "critical"
        assert body["answer_policy"] == "escalation_only"

    def test_evaluate_endpoint_requires_query(self, api_client):
        res = api_client.post("/api/admin/policy/evaluate", json={})
        assert res.status_code == 400

    def test_evaluate_endpoint_with_category(self, api_client):
        res = api_client.post(
            "/api/admin/policy/evaluate",
            json={"query": "식품 잔량은?", "category": "FOOD_TASTING"},
        )
        assert res.status_code == 200
        body = res.get_json()
        assert body["escalation_target"] == "식약처"

    def test_rules_endpoint_returns_rules(self, api_client):
        res = api_client.get("/api/admin/policy/rules")
        assert res.status_code == 200
        body = res.get_json()
        assert "disclaimers" in body
        assert "escalation_directory" in body
        assert body["risk_levels"] == ["low", "medium", "high", "critical"]
