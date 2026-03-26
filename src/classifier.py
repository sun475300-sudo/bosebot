"""질문 의도 분류기 모듈.

사용자 질문을 10개 카테고리 중 하나 이상으로 분류한다.
"""

from src.utils import load_json

CATEGORY_KEYWORDS = {
    "GENERAL": [
        "보세전시장", "보세구역", "제도", "정의", "개념", "뜻", "무엇",
        "어떤 곳", "어떤곳", "보세 전시장"
    ],
    "LICENSE": [
        "특허", "운영", "설치", "허가", "특허기간", "특허신청",
        "특허장소", "운영인", "설영특허"
    ],
    "IMPORT_EXPORT": [
        "반입", "반출", "반출입", "신고", "물품검사", "검사",
        "들여오", "내보내", "가져오", "꺼내"
    ],
    "EXHIBITION": [
        "전시", "장치", "사용", "진열", "디스플레이", "전시회",
        "박람회", "전람회"
    ],
    "SALES": [
        "판매", "직매", "현장판매", "현장 판매", "인도", "구매",
        "매매", "사다", "팔다", "살 수", "현장에서 판매", "바로 판매"
    ],
    "SAMPLE": [
        "견본품", "샘플", "견본", "홍보용", "시료", "무료 배포",
        "무료배포", "나눠주"
    ],
    "FOOD_TASTING": [
        "시식", "식품", "음식", "먹을", "요건확인", "세관장확인",
        "식약처", "검역", "위생", "시식용"
    ],
    "DOCUMENTS": [
        "서류", "신고서", "신청서", "구비서류", "제출", "양식",
        "서식", "첨부", "문서"
    ],
    "PENALTIES": [
        "벌칙", "제재", "과태료", "벌금", "처벌", "위반", "처분",
        "불이익", "과징금"
    ],
    "CONTACT": [
        "문의", "전화", "연락처", "담당", "어디에", "누구에게",
        "상담", "고객지원", "기술지원", "보세산업과"
    ]
}


def classify_query(query: str) -> list[str]:
    """사용자 질문을 카테고리로 분류한다.

    Args:
        query: 사용자 질문 문자열

    Returns:
        매칭된 카테고리 코드 리스트 (최소 1개). 매칭 없으면 ["GENERAL"].
    """
    query_lower = query.lower()
    scores = {}

    for category, keywords in CATEGORY_KEYWORDS.items():
        score = 0
        for keyword in keywords:
            if keyword in query_lower:
                score += 1
        if score > 0:
            scores[category] = score

    if not scores:
        return ["GENERAL"]

    max_score = max(scores.values())
    results = [cat for cat, sc in scores.items() if sc >= max_score]

    return sorted(results)


def get_primary_category(query: str) -> str:
    """사용자 질문의 주요 카테고리 1개를 반환한다."""
    categories = classify_query(query)
    return categories[0]
