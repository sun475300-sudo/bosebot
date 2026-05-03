"""
Korean synonym resolver for the bonded exhibition hall chatbot.

Maps common colloquial/informal Korean terms to their canonical forms
used in the chatbot's FAQ entries and classifier keywords.
"""

SYNONYMS: dict[str, str] = {
    "물건": "물품",
    "팔다": "판매",
    "팔아": "판매",
    # NOTE: single-syllable "팔" removed (matches inside other words).
    "사다": "구매",
    # NOTE: single-syllable "사" removed (matches inside other words).
    "넣다": "반입",
    "넣어": "반입",
    "빼다": "반출",
    # NOTE: single-syllable "빼" removed (matches inside other words).
    "보내다": "반송",
    "보내": "반송",
    "허가": "면허",
    "세금": "관세",
    # NOTE: single-syllable "벌" removed (matches inside other words).
    "잘못": "위반",
    "전화": "연락처",
    "종이": "서류",
    "서류들": "서류",
    "갱신": "연장",
    "쇼": "전시회",
    "맛보기": "시식",
    "시음": "시식",
    "공짜": "무료 배포",
    "보여주다": "전시",
    "전시하다": "전시",
    "ATA Carnet": "ATA 까르네",
    "ATA carnet": "ATA 까르네",
    "ata carnet": "ATA 까르네",
    "카르네": "ATA 까르네",
    "운송신고": "보세운송",
    "통관신고": "수입신고",
    "재반출": "재수출",
    "언제까지": "기한",
    "마감": "기한",
    "며칠까지": "기한",
    "등록": "특허",
    "지정": "특허",
}

_SORTED_KEYS: list[str] = sorted(SYNONYMS.keys(), key=len, reverse=True)


def resolve_synonyms(query: str) -> str:
    """Replace synonym occurrences with canonical forms (longest first)."""
    result = query
    for synonym in _SORTED_KEYS:
        if synonym in result:
            result = result.replace(synonym, SYNONYMS[synonym])
    return result


def expand_query(query: str) -> str:
    """Append canonical terms to *query* while preserving the original text."""
    canonical_terms: list[str] = []
    for synonym in _SORTED_KEYS:
        if synonym in query:
            canonical = SYNONYMS[synonym]
            if canonical not in canonical_terms:
                canonical_terms.append(canonical)

    if not canonical_terms:
        return query

    return query + " " + " ".join(canonical_terms)
