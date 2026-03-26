"""데이터 정합성 검증 모듈.

FAQ ↔ 법령 근거 간 참조 일치 여부, 카테고리 커버리지,
에스컬레이션 규칙 정합성 등을 자동 검증한다.
"""

from src.utils import load_json


def validate_faq_legal_references() -> list[str]:
    """FAQ의 법령 근거가 legal_references.json에 정의되어 있는지 검증한다.

    Returns:
        오류 메시지 리스트 (비어있으면 정합성 통과)
    """
    faq_data = load_json("data/faq.json")
    legal_data = load_json("data/legal_references.json")

    known_references = set()
    for ref in legal_data.get("references", []):
        law_name = ref.get("law_name", "")
        article = ref.get("article", "")
        known_references.add(f"{law_name} {article}".strip())

        sub_articles = ref.get("sub_articles", {})
        for sub_art, sub_title in sub_articles.items():
            known_references.add(f"{law_name} {sub_art}({sub_title})")

    errors = []
    for item in faq_data.get("items", []):
        faq_id = item.get("id", "?")
        for basis in item.get("legal_basis", []):
            matched = False
            for known in known_references:
                if known in basis or basis in known:
                    matched = True
                    break
            # 관세청 FAQ 등 비법령 근거는 검증 제외
            if not matched and "FAQ" not in basis and "안내" not in basis:
                # 부분 매칭 검사: 법령명이 포함되어 있으면 통과
                law_names = [r.get("law_name", "") for r in legal_data.get("references", [])]
                partial_match = any(ln in basis for ln in law_names if ln)
                if not partial_match:
                    errors.append(
                        f"FAQ [{faq_id}]: 법령 근거 '{basis}'가 "
                        f"legal_references.json에 정의되어 있지 않습니다."
                    )

    return errors


def validate_faq_categories() -> list[str]:
    """모든 카테고리에 최소 1개 FAQ가 있는지 검증한다.

    Returns:
        오류 메시지 리스트
    """
    faq_data = load_json("data/faq.json")
    config = load_json("config/chatbot_config.json")

    defined_categories = {cat["code"] for cat in config.get("categories", [])}
    faq_categories = {item["category"] for item in faq_data.get("items", [])}

    errors = []
    for cat in defined_categories:
        if cat not in faq_categories:
            cat_name = next(
                (c["name"] for c in config["categories"] if c["code"] == cat),
                cat
            )
            errors.append(f"카테고리 '{cat_name}'({cat})에 FAQ가 없습니다.")

    return errors


def validate_escalation_targets() -> list[str]:
    """에스컬레이션 규칙의 target이 config의 contacts에 존재하는지 검증한다.

    Returns:
        오류 메시지 리스트
    """
    escalation_data = load_json("data/escalation_rules.json")
    config = load_json("config/chatbot_config.json")

    contacts = set(config.get("contacts", {}).keys())

    errors = []
    for rule in escalation_data.get("rules", []):
        target = rule.get("target", "")
        if target not in contacts:
            errors.append(
                f"에스컬레이션 규칙 [{rule.get('id')}]: "
                f"target '{target}'이 contacts에 정의되어 있지 않습니다."
            )

    return errors


def validate_faq_keywords_not_empty() -> list[str]:
    """FAQ 항목에 키워드가 비어있지 않은지 검증한다.

    Returns:
        오류 메시지 리스트
    """
    faq_data = load_json("data/faq.json")

    errors = []
    for item in faq_data.get("items", []):
        faq_id = item.get("id", "?")
        keywords = item.get("keywords", [])
        if not keywords:
            errors.append(f"FAQ [{faq_id}]: keywords가 비어있습니다.")

    return errors


def run_all_validations() -> dict:
    """모든 정합성 검증을 실행한다.

    Returns:
        {검증명: 오류리스트} 딕셔너리
    """
    return {
        "faq_legal_references": validate_faq_legal_references(),
        "faq_categories": validate_faq_categories(),
        "escalation_targets": validate_escalation_targets(),
        "faq_keywords": validate_faq_keywords_not_empty(),
    }
