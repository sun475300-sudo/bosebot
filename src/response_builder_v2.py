"""Response Builder v2 - Dynamic template composition.

This module composes a structured response from a matched FAQ item plus the
risk-control decision produced by :mod:`src.policy_engine_v2`. Sections are
conditionally included based on the risk level so the final answer matches
the answer-policy semantics (direct / conditional / restricted /
escalation_only).

The builder is pure-Python and has no external dependencies; it intentionally
does not import :mod:`src.response_builder` or rely on runtime state. This
makes it easy to unit-test and safe to call from any request handler.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


# ---------------------------------------------------------------------------
# Risk ordering helpers
# ---------------------------------------------------------------------------

RISK_ORDER: Dict[str, int] = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}


def _risk_level_at_least(risk_level: str, minimum: str) -> bool:
    """Return True if ``risk_level`` is ``>= minimum``."""
    return RISK_ORDER.get(risk_level, 0) >= RISK_ORDER.get(minimum, 0)


# ---------------------------------------------------------------------------
# Canonical texts (Korean)
# ---------------------------------------------------------------------------

DEFAULT_DISCLAIMER = (
    "본 답변은 일반적인 안내용 설명이며, 구체적인 사실관계에 따라 달라질 수 있습니다. "
    "최종 처리는 관할 세관 또는 해당 소관기관 확인이 필요합니다."
)

RISK_DISCLAIMERS: Dict[str, str] = {
    "low": "본 답변은 일반 안내이며 상세 내용은 공식 자료를 참고해 주세요.",
    "medium": "개별 사안은 관할 세관 확인이 필요합니다.",
    "high": (
        "본 답변은 법적 효력이 없으며, 구체적 사안은 관할 세관 확인이 필요합니다."
    ),
    "critical": (
        "본 질의는 챗봇이 최종 판단할 수 없으며, "
        "관할 세관 또는 전문가 상담이 필요합니다."
    ),
}


ESCALATION_DIRECTORY: Dict[str, Dict[str, str]] = {
    "관할 세관": {
        "name": "관할 세관",
        "phone": "1344-5100",
        "department": "관세청 관할 세관 통관부서",
    },
    "보세산업과": {
        "name": "관세청 통관국 보세산업과",
        "phone": "125",
        "department": "보세산업과",
    },
    "식약처": {
        "name": "식품의약품안전처",
        "phone": "1577-1255",
        "department": "식약처 민원실",
    },
    "125": {
        "name": "관세청 고객지원센터",
        "phone": "125",
        "department": "고객지원센터",
    },
    "customer_support": {
        "name": "관세청 고객지원센터",
        "phone": "125",
        "department": "고객지원센터",
    },
}


UNKNOWN_HEADLINE = (
    "현재 확인한 공식 자료만으로는 단정적으로 답변드리기 어렵습니다."
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _as_list(value: Any) -> List[str]:
    """Coerce ``value`` to a list of stripped non-empty strings."""
    if value is None:
        return []
    if isinstance(value, str):
        parts = [p.strip() for p in value.splitlines()]
        return [p for p in parts if p]
    if isinstance(value, Iterable):
        out: List[str] = []
        for item in value:
            if item is None:
                continue
            s = str(item).strip()
            if s:
                out.append(s)
        return out
    s = str(value).strip()
    return [s] if s else []


def _one_liner(text: str) -> str:
    """Collapse ``text`` into a single-line summary."""
    if not text:
        return ""
    return " ".join(text.split())


def _first_sentence(text: str) -> str:
    """Return the first sentence (up to the first period) from ``text``."""
    if not text:
        return ""
    flat = _one_liner(text)
    for sep in ("다. ", "요. ", "니다. ", ". "):
        idx = flat.find(sep)
        if idx != -1:
            return flat[: idx + len(sep.rstrip())].strip()
    return flat


def _escalation_contact(target: Optional[str]) -> Dict[str, str]:
    if not target:
        return {}
    info = ESCALATION_DIRECTORY.get(target)
    if info is not None:
        return dict(info)
    # Unknown target - return a minimal stub so markdown/plain formatters still
    # have something to render.
    return {"name": target, "phone": "", "department": ""}


# ---------------------------------------------------------------------------
# ResponseBuilderV2
# ---------------------------------------------------------------------------


class ResponseBuilderV2:
    """Compose a structured response from FAQ + policy decision.

    The builder returns a dict with a stable shape::

        {
            "kind": "answer" | "escalation_only" | "unknown",
            "risk_level": "low|medium|high|critical",
            "answer_policy": "direct|conditional|restricted|escalation_only",
            "sections": {
                "summary": str | None,
                "explanation": list[str] | None,
                "conditions": list[str] | None,
                "procedure": list[str] | None,
                "legal_basis": list[str] | None,
                "related_faqs": list[dict] | None,
                "disclaimer": str,
                "escalation": dict | None,
            },
            "section_order": list[str],
            "meta": {...},
        }

    Only sections that apply at the current risk level are populated; the rest
    are omitted from ``section_order`` so callers/formatters don't have to
    second-guess composition rules.
    """

    VERSION = "2.0.0"

    def __init__(self) -> None:
        self.version = self.VERSION

    # -----------------------------------------------------------------
    # Primary entry point
    # -----------------------------------------------------------------

    def build(
        self,
        faq_item: Optional[Dict[str, Any]],
        policy_result: Optional[Dict[str, Any]] = None,
        entities: Optional[List[Dict[str, Any]]] = None,
        related: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Return a structured response for a matched FAQ.

        Args:
            faq_item: The matched FAQ item (dict with ``question``, ``answer``,
                ``legal_basis`` etc.). If ``None`` the builder returns the
                unknown response.
            policy_result: Decision from :class:`PolicyEngineV2.evaluate`. When
                omitted the builder assumes ``low`` risk / ``direct`` policy.
            entities: Optional extracted entities - stored in ``meta`` for
                observability but not rendered.
            related: Optional list of related FAQ dicts (``id`` + ``question``).

        Returns:
            Structured response dictionary.
        """
        if not faq_item:
            query = ""
            if isinstance(policy_result, dict):
                query = policy_result.get("query", "") or ""
            return self.build_unknown(query)

        policy = self._normalize_policy(policy_result)
        risk_level = policy["risk_level"]
        answer_policy = policy["answer_policy"]
        escalation_target = policy.get("escalation_target")

        # escalation_only => short-circuit to escalation-only template
        if answer_policy == "escalation_only" or risk_level == "critical":
            return self.build_escalation_only(
                escalation_target or "125",
                faq_item=faq_item,
                policy_result=policy,
            )

        sections: Dict[str, Any] = {}
        order: List[str] = []

        # --- summary (always) ---
        summary = self._compose_summary(faq_item)
        sections["summary"] = summary
        order.append("summary")

        # --- explanation (low+ => always when present) ---
        explanation = self._compose_explanation(faq_item)
        if explanation and _risk_level_at_least(risk_level, "low"):
            sections["explanation"] = explanation
            order.append("explanation")

        # --- conditions (medium+) ---
        if _risk_level_at_least(risk_level, "medium"):
            conditions = self._compose_conditions(faq_item, policy)
            if conditions:
                sections["conditions"] = conditions
                order.append("conditions")

        # --- procedure (medium+) ---
        if _risk_level_at_least(risk_level, "medium"):
            procedure = self._compose_procedure(faq_item)
            if procedure:
                sections["procedure"] = procedure
                order.append("procedure")

        # --- legal basis (always if present) ---
        legal_basis = _as_list(faq_item.get("legal_basis"))
        if legal_basis:
            sections["legal_basis"] = legal_basis
            order.append("legal_basis")

        # --- related FAQs (optional) ---
        related_rendered = self._compose_related(related)
        if related_rendered:
            sections["related_faqs"] = related_rendered
            order.append("related_faqs")

        # --- disclaimer (always) ---
        sections["disclaimer"] = self._compose_disclaimer(policy)
        order.append("disclaimer")

        # --- escalation (high+) ---
        if _risk_level_at_least(risk_level, "high") and escalation_target:
            sections["escalation"] = _escalation_contact(escalation_target)
            order.append("escalation")

        return {
            "kind": "answer",
            "risk_level": risk_level,
            "answer_policy": answer_policy,
            "sections": sections,
            "section_order": order,
            "meta": {
                "builder_version": self.VERSION,
                "faq_id": faq_item.get("id"),
                "category": faq_item.get("category"),
                "entities": list(entities or []),
                "reasons": list(policy.get("reasons") or []),
            },
        }

    # -----------------------------------------------------------------
    # Escalation-only / unknown templates
    # -----------------------------------------------------------------

    def build_escalation_only(
        self,
        escalation_target: str,
        faq_item: Optional[Dict[str, Any]] = None,
        policy_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Return a critical-case response that only points to an agency."""
        policy = self._normalize_policy(policy_result)
        # Force a critical/escalation_only shape for this template.
        policy["risk_level"] = "critical"
        policy["answer_policy"] = "escalation_only"
        policy["escalation_target"] = escalation_target or policy.get(
            "escalation_target"
        )

        summary = (
            "본 문의는 챗봇이 최종 판단할 수 있는 사안이 아니므로 "
            "담당 기관 안내를 참고해 주세요."
        )
        disclaimer = self._compose_disclaimer(policy)
        escalation = _escalation_contact(policy["escalation_target"])

        sections: Dict[str, Any] = {
            "summary": summary,
            "disclaimer": disclaimer,
            "escalation": escalation or {"name": escalation_target or ""},
        }
        order = ["summary", "disclaimer", "escalation"]

        meta: Dict[str, Any] = {
            "builder_version": self.VERSION,
            "faq_id": faq_item.get("id") if faq_item else None,
            "category": faq_item.get("category") if faq_item else None,
            "reasons": list(policy.get("reasons") or []),
        }

        return {
            "kind": "escalation_only",
            "risk_level": "critical",
            "answer_policy": "escalation_only",
            "sections": sections,
            "section_order": order,
            "meta": meta,
        }

    def build_unknown(self, query: str) -> Dict[str, Any]:
        """Return the unmatched-query template."""
        summary = UNKNOWN_HEADLINE
        explanation = [
            (
                "구체적인 물품 성질, 반입 목적, 판매 여부, 행사 방식, "
                "신고 내용에 따라 결과가 달라질 수 있습니다."
            ),
            "관할 세관 또는 관세청 고객지원센터(125)로 문의해 주세요.",
        ]
        sections: Dict[str, Any] = {
            "summary": summary,
            "explanation": explanation,
            "disclaimer": DEFAULT_DISCLAIMER,
            "escalation": _escalation_contact("125"),
        }
        order = ["summary", "explanation", "disclaimer", "escalation"]

        return {
            "kind": "unknown",
            "risk_level": "low",
            "answer_policy": "direct",
            "sections": sections,
            "section_order": order,
            "meta": {
                "builder_version": self.VERSION,
                "query": query or "",
            },
        }

    # -----------------------------------------------------------------
    # Formatters
    # -----------------------------------------------------------------

    def format_markdown(self, response: Dict[str, Any]) -> str:
        """Render ``response`` as GitHub-flavoured markdown."""
        sections = response.get("sections", {}) or {}
        order = response.get("section_order") or list(sections.keys())
        lines: List[str] = []

        for name in order:
            value = sections.get(name)
            if value is None or value == "" or value == []:
                continue

            if name == "summary":
                lines.append("## 결론")
                lines.append(str(value))
            elif name == "explanation":
                lines.append("## 설명")
                for i, item in enumerate(_as_list(value), 1):
                    lines.append(f"{i}. {item}")
            elif name == "conditions":
                lines.append("## 조건")
                for item in _as_list(value):
                    lines.append(f"- 다만 {item}")
            elif name == "procedure":
                lines.append("## 절차")
                for i, item in enumerate(_as_list(value), 1):
                    lines.append(f"{i}. {item}")
            elif name == "legal_basis":
                lines.append("## 법적 근거")
                for item in _as_list(value):
                    lines.append(f"- {item}")
            elif name == "related_faqs":
                lines.append("## 관련 FAQ")
                for faq in value:
                    q = faq.get("question", "") if isinstance(faq, dict) else str(faq)
                    fid = faq.get("id", "") if isinstance(faq, dict) else ""
                    if fid:
                        lines.append(f"- [{fid}] {q}")
                    else:
                        lines.append(f"- {q}")
            elif name == "disclaimer":
                lines.append("## 안내")
                lines.append(f"> {value}")
            elif name == "escalation":
                lines.append("## 담당 기관 안내")
                contact = value if isinstance(value, dict) else {}
                name_s = contact.get("name", "")
                phone = contact.get("phone", "")
                dept = contact.get("department", "")
                if name_s:
                    lines.append(f"- 기관: **{name_s}**")
                if dept:
                    lines.append(f"- 부서: {dept}")
                if phone:
                    lines.append(f"- 연락처: {phone}")
            lines.append("")

        return "\n".join(lines).rstrip() + "\n"

    def format_plain(self, response: Dict[str, Any]) -> str:
        """Render ``response`` as plain text (no markdown)."""
        sections = response.get("sections", {}) or {}
        order = response.get("section_order") or list(sections.keys())
        lines: List[str] = []

        for name in order:
            value = sections.get(name)
            if value is None or value == "" or value == []:
                continue

            if name == "summary":
                lines.append("[결론]")
                lines.append(str(value))
            elif name == "explanation":
                lines.append("[설명]")
                for i, item in enumerate(_as_list(value), 1):
                    lines.append(f"{i}. {item}")
            elif name == "conditions":
                lines.append("[조건]")
                for item in _as_list(value):
                    lines.append(f"- 다만 {item}")
            elif name == "procedure":
                lines.append("[절차]")
                for i, item in enumerate(_as_list(value), 1):
                    lines.append(f"{i}. {item}")
            elif name == "legal_basis":
                lines.append("[법적 근거]")
                for item in _as_list(value):
                    lines.append(f"- {item}")
            elif name == "related_faqs":
                lines.append("[관련 FAQ]")
                for faq in value:
                    q = faq.get("question", "") if isinstance(faq, dict) else str(faq)
                    fid = faq.get("id", "") if isinstance(faq, dict) else ""
                    if fid:
                        lines.append(f"- [{fid}] {q}")
                    else:
                        lines.append(f"- {q}")
            elif name == "disclaimer":
                lines.append("[안내]")
                lines.append(str(value))
            elif name == "escalation":
                lines.append("[담당 기관 안내]")
                contact = value if isinstance(value, dict) else {}
                name_s = contact.get("name", "")
                phone = contact.get("phone", "")
                dept = contact.get("department", "")
                if name_s:
                    lines.append(f"- 기관: {name_s}")
                if dept:
                    lines.append(f"- 부서: {dept}")
                if phone:
                    lines.append(f"- 연락처: {phone}")
            lines.append("")

        return "\n".join(lines).rstrip() + "\n"

    # -----------------------------------------------------------------
    # Section composers
    # -----------------------------------------------------------------

    def _compose_summary(self, faq_item: Dict[str, Any]) -> str:
        """Single-line conclusion drawn from the FAQ answer."""
        summary = faq_item.get("summary") or faq_item.get("conclusion")
        if summary:
            return _one_liner(str(summary))

        answer = faq_item.get("answer", "")
        if not answer:
            q = faq_item.get("question", "")
            return _one_liner(q) or UNKNOWN_HEADLINE
        return _first_sentence(answer)

    def _compose_explanation(self, faq_item: Dict[str, Any]) -> List[str]:
        """Detailed explanation paragraphs."""
        if "explanation" in faq_item and faq_item["explanation"]:
            return _as_list(faq_item["explanation"])

        answer = faq_item.get("answer")
        if not answer:
            return []
        first = _first_sentence(answer)
        flat = _one_liner(str(answer))
        if first and flat.startswith(first) and len(flat) > len(first):
            remainder = flat[len(first) :].strip()
            if remainder:
                return [remainder]
            return []
        return [flat] if flat else []

    def _compose_conditions(
        self, faq_item: Dict[str, Any], policy: Dict[str, Any]
    ) -> List[str]:
        """Conditions rendered with a ``다만 X인 경우`` prefix."""
        raw = faq_item.get("conditions")
        conds = _as_list(raw)
        if conds:
            return conds

        # Fall back to notes when the FAQ has no explicit conditions block but
        # the risk level demands caveats.
        notes = faq_item.get("notes")
        if notes:
            return _as_list(notes)

        # As a last resort, derive generic caveats from the policy restrictions.
        derived: List[str] = []
        if "requires_agency_verification" in (policy.get("restrictions") or []):
            derived.append("관할 세관 확인이 필요한 경우")
        if "no_definitive_judgment" in (policy.get("restrictions") or []):
            derived.append("법적 효력 판단이 필요한 경우")
        return derived

    def _compose_procedure(self, faq_item: Dict[str, Any]) -> List[str]:
        """Step-by-step procedure items."""
        raw = faq_item.get("procedure") or faq_item.get("steps")
        return _as_list(raw)

    def _compose_related(
        self, related: Optional[List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """Keep up to 3 related FAQs in a compact dict shape."""
        if not related:
            return []
        out: List[Dict[str, Any]] = []
        for item in related[:3]:
            if not isinstance(item, dict):
                continue
            fid = item.get("id") or item.get("faq_id")
            question = item.get("question") or item.get("q") or ""
            if not fid and not question:
                continue
            out.append({"id": fid, "question": question})
        return out

    def _compose_disclaimer(self, policy: Dict[str, Any]) -> str:
        """Pick the disclaimer text that best matches the policy."""
        required = policy.get("required_disclaimers") or []
        if required:
            # Join with a single space - consumers expect one string.
            return " ".join(str(x).strip() for x in required if x).strip()
        risk = policy.get("risk_level", "low")
        return RISK_DISCLAIMERS.get(risk, DEFAULT_DISCLAIMER)

    # -----------------------------------------------------------------
    # Utility
    # -----------------------------------------------------------------

    @staticmethod
    def _normalize_policy(
        policy_result: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Return a defensive copy of ``policy_result`` with defaults."""
        base: Dict[str, Any] = {
            "risk_level": "low",
            "answer_policy": "direct",
            "restrictions": [],
            "required_disclaimers": [],
            "escalation_required": False,
            "escalation_target": None,
            "confidence": 0.85,
            "reasons": [],
        }
        if isinstance(policy_result, dict):
            base.update({k: v for k, v in policy_result.items() if v is not None})
        # Make sure the mandatory fields have the right shape.
        risk = str(base.get("risk_level") or "low").lower()
        if risk not in RISK_ORDER:
            risk = "low"
        base["risk_level"] = risk
        if base.get("answer_policy") is None:
            base["answer_policy"] = "direct"
        if not isinstance(base.get("restrictions"), list):
            base["restrictions"] = []
        if not isinstance(base.get("required_disclaimers"), list):
            base["required_disclaimers"] = []
        if not isinstance(base.get("reasons"), list):
            base["reasons"] = []
        return base


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_singleton: Optional[ResponseBuilderV2] = None


def get_response_builder_v2() -> ResponseBuilderV2:
    """Return a process-wide :class:`ResponseBuilderV2` singleton."""
    global _singleton
    if _singleton is None:
        _singleton = ResponseBuilderV2()
    return _singleton
