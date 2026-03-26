"""답변 생성기 모듈.

템플릿 기반으로 구조화된 답변을 조립한다.
"""

from src.utils import load_json


def load_response_template() -> dict:
    """답변 템플릿을 로드한다."""
    data = load_json("templates/response_template.json")
    return data.get("structure", {})


def build_response(
    topic: str,
    conclusion: str,
    explanation: list[str],
    legal_basis: list[str],
    confirmation_items: list[str] | None = None,
    is_escalation: bool = False,
    escalation_message: str = "",
) -> str:
    """구조화된 답변 문자열을 생성한다.

    Args:
        topic: 질문 주제
        conclusion: 한 줄 결론
        explanation: 설명 항목 리스트
        legal_basis: 법적 근거 리스트
        confirmation_items: 확인 필요 항목 리스트 (선택)
        is_escalation: 에스컬레이션 여부
        escalation_message: 에스컬레이션 안내 메시지

    Returns:
        포맷된 답변 문자열
    """
    parts = []

    parts.append(f"문의하신 내용은 [{topic}]에 관한 사항입니다.")
    parts.append("")

    parts.append("결론:")
    parts.append(f"- {conclusion}")
    parts.append("")

    if explanation:
        parts.append("설명:")
        for i, item in enumerate(explanation, 1):
            parts.append(f"{i}. {item}")
        parts.append("")

    if confirmation_items:
        parts.append("민원인이 확인할 사항:")
        for item in confirmation_items:
            parts.append(f"- {item}")
        parts.append("")

    if legal_basis:
        parts.append("근거:")
        for basis in legal_basis:
            parts.append(f"- {basis}")
        parts.append("")

    if is_escalation and escalation_message:
        parts.append("추가 안내:")
        parts.append(f"- {escalation_message}")
        parts.append("")

    parts.append("안내:")
    parts.append("- 본 답변은 일반적인 안내용 설명이며, 구체적인 사실관계에 따라 달라질 수 있습니다.")
    parts.append("- 최종 처리는 관할 세관 또는 해당 소관기관 확인이 필요합니다.")

    return "\n".join(parts)


def build_unknown_response(query: str) -> str:
    """매칭되는 FAQ가 없을 때의 기본 답변을 생성한다."""
    return (
        "현재 확인한 공식 자료만으로는 단정하기 어렵습니다.\n"
        "\n"
        "구체적인 물품 성질, 반입 목적, 판매 여부, 행사 방식, "
        "신고 내용에 따라 달라질 수 있습니다.\n"
        "\n"
        "추가 안내:\n"
        "- 관세청 고객지원센터(125)로 문의하시거나,\n"
        "- 관할 세관에 직접 확인하시기 바랍니다.\n"
        "\n"
        "안내:\n"
        "- 본 답변은 일반적인 안내용 설명이며, 구체적인 사실관계에 따라 달라질 수 있습니다.\n"
        "- 최종 처리는 관할 세관 또는 해당 소관기관 확인이 필요합니다."
    )
