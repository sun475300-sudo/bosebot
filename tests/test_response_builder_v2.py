"""Tests for :mod:`src.response_builder_v2`."""

from __future__ import annotations

import pytest

from src.policy_engine_v2 import PolicyEngineV2
from src.response_builder_v2 import (
    DEFAULT_DISCLAIMER,
    ResponseBuilderV2,
    get_response_builder_v2,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def builder() -> ResponseBuilderV2:
    return ResponseBuilderV2()


@pytest.fixture
def policy_engine() -> PolicyEngineV2:
    return PolicyEngineV2()


@pytest.fixture
def faq_item() -> dict:
    return {
        "id": "A",
        "category": "GENERAL",
        "question": "보세전시장이 무엇인가요?",
        "answer": (
            "보세전시장은 박람회, 전람회 등의 운영을 위해 외국물품을 "
            "장치·전시·사용할 수 있는 보세구역입니다. "
            "일반 창고나 행사장과 달리 전시 목적의 외국물품을 통제 아래 둘 수 있습니다."
        ),
        "legal_basis": ["관세법 제190조"],
        "notes": "",
        "keywords": ["보세전시장", "정의"],
    }


@pytest.fixture
def faq_item_with_procedure() -> dict:
    return {
        "id": "B",
        "category": "LEGAL",
        "question": "보세전시장 반입 신고 절차는?",
        "answer": "보세전시장 반입 시에는 일정 절차를 따라야 합니다.",
        "legal_basis": ["관세법 제190조", "관세법 시행령 제101조"],
        "conditions": ["전시 종료 후 처분이 필요한 경우"],
        "procedure": [
            "반입 신고서 작성",
            "관할 세관 제출",
            "반입 승인 후 장치",
        ],
    }


@pytest.fixture
def related_faqs() -> list:
    return [
        {"id": "F", "question": "관련 FAQ 1?"},
        {"id": "G", "question": "관련 FAQ 2?"},
        {"id": "H", "question": "관련 FAQ 3?"},
        {"id": "I", "question": "초과 FAQ"},
    ]


# ---------------------------------------------------------------------------
# Section composition per risk level
# ---------------------------------------------------------------------------


class TestSectionComposition:
    def test_low_risk_has_summary_explanation_legal_disclaimer(
        self, builder, faq_item, policy_engine
    ):
        policy = policy_engine.evaluate("보세전시장이 무엇인가요?")
        assert policy["risk_level"] == "low"
        res = builder.build(faq_item, policy_result=policy)

        assert res["kind"] == "answer"
        assert "summary" in res["sections"]
        assert "explanation" in res["sections"]
        assert "legal_basis" in res["sections"]
        assert "disclaimer" in res["sections"]
        # conditions/procedure/escalation should not appear at low risk
        assert "conditions" not in res["sections"]
        assert "procedure" not in res["sections"]
        assert "escalation" not in res["sections"]

    def test_medium_risk_adds_conditions_and_procedure(
        self, builder, faq_item_with_procedure
    ):
        policy = {
            "risk_level": "medium",
            "answer_policy": "conditional",
            "restrictions": [],
            "required_disclaimers": [],
            "escalation_target": None,
            "reasons": [],
        }
        res = builder.build(faq_item_with_procedure, policy_result=policy)

        assert res["risk_level"] == "medium"
        assert "conditions" in res["sections"]
        assert "procedure" in res["sections"]
        assert res["sections"]["procedure"][0] == "반입 신고서 작성"
        # No escalation at medium
        assert "escalation" not in res["sections"]

    def test_high_risk_includes_escalation_and_conditions(
        self, builder, faq_item_with_procedure
    ):
        policy = {
            "risk_level": "high",
            "answer_policy": "restricted",
            "restrictions": ["no_definitive_judgment", "requires_agency_verification"],
            "required_disclaimers": ["본 답변은 법적 효력이 없습니다."],
            "escalation_target": "관할 세관",
            "reasons": ["legal_judgment_request"],
        }
        res = builder.build(faq_item_with_procedure, policy_result=policy)

        assert res["risk_level"] == "high"
        assert "conditions" in res["sections"]
        assert "procedure" in res["sections"]
        assert "escalation" in res["sections"]
        contact = res["sections"]["escalation"]
        assert contact["name"] == "관할 세관"
        assert contact["phone"] == "1344-5100"

    def test_critical_forces_escalation_only(self, builder, faq_item):
        policy = {
            "risk_level": "critical",
            "answer_policy": "escalation_only",
            "restrictions": ["no_definitive_judgment"],
            "escalation_target": "125",
            "reasons": ["sensitive_keyword"],
        }
        res = builder.build(faq_item, policy_result=policy)

        assert res["kind"] == "escalation_only"
        assert res["answer_policy"] == "escalation_only"
        # Critical template deliberately strips explanation/procedure
        assert "explanation" not in res["sections"]
        assert "procedure" not in res["sections"]
        assert "escalation" in res["sections"]

    def test_no_policy_defaults_to_low(self, builder, faq_item):
        res = builder.build(faq_item)
        assert res["risk_level"] == "low"
        assert "summary" in res["sections"]
        assert "escalation" not in res["sections"]


# ---------------------------------------------------------------------------
# Escalation-only response
# ---------------------------------------------------------------------------


class TestEscalationOnly:
    def test_build_escalation_only_basic(self, builder):
        res = builder.build_escalation_only("관할 세관")
        assert res["kind"] == "escalation_only"
        assert res["risk_level"] == "critical"
        assert res["answer_policy"] == "escalation_only"
        assert "summary" in res["sections"]
        assert "escalation" in res["sections"]
        assert res["sections"]["escalation"]["name"] == "관할 세관"

    def test_build_escalation_only_with_unknown_target(self, builder):
        res = builder.build_escalation_only("상공회의소")
        assert res["sections"]["escalation"]["name"] == "상공회의소"

    def test_build_escalation_only_disclaimer_always_present(self, builder):
        res = builder.build_escalation_only("125")
        assert res["sections"]["disclaimer"]

    def test_build_escalation_only_plain_format(self, builder):
        res = builder.build_escalation_only("관할 세관")
        plain = builder.format_plain(res)
        assert "담당 기관 안내" in plain
        assert "1344-5100" in plain


# ---------------------------------------------------------------------------
# Unknown response
# ---------------------------------------------------------------------------


class TestBuildUnknown:
    def test_build_unknown_basic(self, builder):
        res = builder.build_unknown("보세전시장에서 뭔가 이상한 일이?")
        assert res["kind"] == "unknown"
        assert "summary" in res["sections"]
        assert "disclaimer" in res["sections"]
        assert "escalation" in res["sections"]

    def test_build_unknown_without_query(self, builder):
        res = builder.build_unknown("")
        assert res["kind"] == "unknown"
        assert "단정" in res["sections"]["summary"]

    def test_build_without_faq_returns_unknown(self, builder):
        res = builder.build(None)
        assert res["kind"] == "unknown"


# ---------------------------------------------------------------------------
# Markdown / plain formatters
# ---------------------------------------------------------------------------


class TestFormatMarkdown:
    def test_markdown_headers_and_summary(self, builder, faq_item):
        res = builder.build(faq_item)
        md = builder.format_markdown(res)
        assert "## 결론" in md
        assert "## 안내" in md
        assert "## 법적 근거" in md
        assert "관세법 제190조" in md

    def test_markdown_escalation_bolds_agency(self, builder, faq_item_with_procedure):
        policy = {
            "risk_level": "high",
            "answer_policy": "restricted",
            "restrictions": ["requires_agency_verification"],
            "escalation_target": "식약처",
            "reasons": [],
        }
        res = builder.build(faq_item_with_procedure, policy_result=policy)
        md = builder.format_markdown(res)
        assert "## 담당 기관 안내" in md
        assert "**식품의약품안전처**" in md
        assert "1577-1255" in md

    def test_plain_format_strips_markdown(self, builder, faq_item):
        res = builder.build(faq_item)
        plain = builder.format_plain(res)
        assert "[결론]" in plain
        assert "[안내]" in plain
        assert "##" not in plain
        assert "**" not in plain


# ---------------------------------------------------------------------------
# Related FAQs
# ---------------------------------------------------------------------------


class TestRelatedFAQs:
    def test_related_included_at_most_three(
        self, builder, faq_item, related_faqs
    ):
        res = builder.build(faq_item, related=related_faqs)
        assert "related_faqs" in res["sections"]
        assert len(res["sections"]["related_faqs"]) == 3

    def test_related_omitted_when_empty(self, builder, faq_item):
        res = builder.build(faq_item, related=[])
        assert "related_faqs" not in res["sections"]

    def test_related_rendered_in_markdown(
        self, builder, faq_item, related_faqs
    ):
        res = builder.build(faq_item, related=related_faqs)
        md = builder.format_markdown(res)
        assert "## 관련 FAQ" in md
        assert "[F] 관련 FAQ 1?" in md


# ---------------------------------------------------------------------------
# Disclaimer semantics
# ---------------------------------------------------------------------------


class TestDisclaimer:
    def test_disclaimer_always_present(self, builder, faq_item):
        res = builder.build(faq_item)
        assert res["sections"]["disclaimer"]

    def test_disclaimer_uses_policy_required(self, builder, faq_item):
        policy = {
            "risk_level": "medium",
            "answer_policy": "conditional",
            "required_disclaimers": ["개별 사안은 관할 세관 확인 필요"],
        }
        res = builder.build(faq_item, policy_result=policy)
        assert "관할 세관" in res["sections"]["disclaimer"]

    def test_unknown_response_has_default_disclaimer(self, builder):
        res = builder.build_unknown("질문")
        assert res["sections"]["disclaimer"] == DEFAULT_DISCLAIMER


# ---------------------------------------------------------------------------
# Singleton / misc
# ---------------------------------------------------------------------------


class TestSingleton:
    def test_get_response_builder_v2_returns_same_instance(self):
        a = get_response_builder_v2()
        b = get_response_builder_v2()
        assert a is b
        assert a.version == "2.0.0"


# ---------------------------------------------------------------------------
# API integration
# ---------------------------------------------------------------------------


class TestAPIIntegration:
    @pytest.fixture
    def client(self):
        import os
        os.environ.setdefault("TESTING", "1")
        from web_server import app
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_chat_v2_engine_returns_structured_response(self, client):
        resp = client.post(
            "/api/chat?engine=v2",
            json={"query": "보세전시장이 무엇인가요?"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("engine") == "v2"
        assert "structured_response" in data
        structured = data["structured_response"]
        assert "sections" in structured
        assert "disclaimer" in structured["sections"]

    def test_chat_format_markdown_sets_answer(self, client):
        resp = client.post(
            "/api/chat?engine=v2&format=markdown",
            json={"query": "보세전시장이 무엇인가요?"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("format") == "markdown"
        assert "## " in data.get("answer", "")

    def test_chat_format_plain(self, client):
        resp = client.post(
            "/api/chat?engine=v2&format=plain",
            json={"query": "보세전시장이 무엇인가요?"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("format") == "plain"
        assert "[결론]" in data.get("answer", "")
