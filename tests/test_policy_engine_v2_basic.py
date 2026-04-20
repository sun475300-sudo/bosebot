"""Policy Engine v2 기본 테스트."""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.policy_engine_v2 import PolicyEngineV2


@pytest.fixture
def engine():
    return PolicyEngineV2()


class TestPolicyEngineV2:
    def test_basic_query_low_risk(self, engine):
        r = engine.evaluate("보세전시장이 뭔가요?")
        assert r["risk_level"] == "low"
        assert r["answer_policy"] == "direct"

    def test_legal_judgment_high_risk(self, engine):
        r = engine.evaluate("이거 위법인가요?")
        assert r["risk_level"] in ("high", "critical")

    def test_sensitive_keyword_critical(self, engine):
        r = engine.evaluate("밀수 하려면 어떻게 해요?")
        assert r["risk_level"] == "critical"
        assert r["escalation_required"] is True

    def test_tax_determination_high(self, engine):
        r = engine.evaluate("관세는 얼마 내나요?")
        assert r["risk_level"] in ("medium", "high")

    def test_food_tasting_multi_agency(self, engine):
        r = engine.evaluate("시식 가능한가요?", category="FOOD_TASTING")
        assert r["risk_level"] in ("medium", "high")

    def test_returns_structure(self, engine):
        r = engine.evaluate("질문")
        assert "risk_level" in r
        assert "answer_policy" in r
        assert "required_disclaimers" in r
        assert "escalation_required" in r
        assert "confidence" in r

    def test_disclaimer_always_present(self, engine):
        r = engine.evaluate("질문")
        assert len(r["required_disclaimers"]) >= 1

    def test_empty_query(self, engine):
        r = engine.evaluate("")
        assert "risk_level" in r

    def test_none_query(self, engine):
        r = engine.evaluate(None)
        assert "risk_level" in r
