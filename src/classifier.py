"""질문 의도 분류기 모듈.

사용자 질문을 13개 카테고리 중 하나 이상으로 분류한다.
또한 새 30-intent 시스템도 지원한다.

수정 이력 (live_chatbot_test_20260504 회귀):
- PATENT, INSPECTION, PATENT_INFRINGEMENT 카테고리 신설
- FOOD_TASTING 매칭 조건을 "시식" 키워드 필수 조건으로 강화
  (단순 "검사", "식품" 단독 매치만으로는 더 이상 트리거되지 않음)
- patent_duration / patent_infringement / goods_inspection 등 fast-path
  의도 룰 추가 (낮은 신뢰도 환경에서도 강하게 동작)
"""

import logging
import re
from typing import Optional

from src.utils import normalize_query, load_json

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 카테고리 키워드
# ---------------------------------------------------------------------------
CATEGORY_KEYWORDS = {
    "GENERAL": [
        "보세전시장", "보세구역", "제도", "정의", "개념", "뜻", "무엇",
        "어떤 곳", "어떤곳", "보세 전시장", "보세창고", "차이", "다른 점",
        "내국물품", "국산", "비교", "구분", "이용", "누가", "자격"
    ],
    # PATENT는 새 카테고리 — "특허"의 모든 측면을 흡수
    "PATENT": [
        "특허", "특허기간", "특허 기간", "특허 신청", "특허신청",
        "특허 갱신", "특허갱신", "특허 연장", "특허 변경", "특허변경",
        "특허 취소", "특허취소", "특허 폐쇄", "특허 박탈",
        "특허 면허", "운영 특허", "설치 특허", "설치특허",
        "특허 수수료", "갱신", "연장",
        "존속기간", "유효기간", "특허 심사",
    ],
    # LICENSE는 PATENT의 alias — 기존 호환을 위해 유지
    "LICENSE": [
        "특허", "운영", "설치", "특허기간", "특허신청",
        "특허장소", "운영인", "설치특허", "갱신", "연장", "변경",
        "특허 연장", "기간 연장"
    ],
    "IMPORT_EXPORT": [
        "반입", "반출", "반출입",
        "들여오", "내보내", "가져오", "꺼내", "재반출", "반송",
        "돌려보내", "잔류", "남은 물품", "미반출",
        "해외로", "세관 검사",
    ],
    # INSPECTION은 새 카테고리 — 물품 검사 절차 일반
    "INSPECTION": [
        "물품 검사", "물품검사", "검사 절차", "검사절차",
        "정기 검사", "정기검사", "무작위 검사", "무작위검사",
        "검사 거부", "검사 어떻게", "검사 진행", "검사 방법",
        "세관 검사", "세관검사", "반입 검사", "반입검사",
    ],
    "EXHIBITION": [
        "전시", "장치", "진열", "디스플레이", "전시회",
        "박람회", "전람회", "시연", "데모", "시범", "체험",
        "사용 범위", "전시 목적", "전시 가능"
    ],
    "SALES": [
        "판매", "직매", "현장판매", "현장 판매", "인도", "구매",
        "매매", "사다", "팔다", "팔 수", "물건 팔", "살 수",
        "현장에서 판매", "바로 판매",
        "계약", "주문", "인도 시점", "통관 후"
    ],
    "SAMPLE": [
        "견본품", "샘플", "견본", "홍보용", "시료", "무료 배포",
        "무료배포", "나눠주", "견본품 관세", "견본품 세금", "견본품 과세"
    ],
    # FOOD_TASTING은 매칭 조건을 시식 컨텍스트로 한정한다.
    # 단순 "식품" 또는 "검사" 단독으로는 매치되지 않는다 (Q7 회귀 방지).
    "FOOD_TASTING": [
        "시식", "시식용", "시식 행사", "시식용 식품", "시식 신고",
        "남은 식품", "잔량 폐기", "식품 잔량", "한글 라벨",
        "요건확인", "세관장확인", "식약처", "검역", "위생",
    ],
    "DOCUMENTS": [
        "서류", "신고서", "신청서", "구비서류", "제출", "양식",
        "서식", "첨부", "문서", "반출입신고서", "허가 신청"
    ],
    "PENALTIES": [
        "벌칙", "제재", "과태료", "벌금", "처벌", "위반", "처분",
        "불이익", "과징금", "무허가", "밀수",
        "업무 정지", "의무 위반", "허가 없이", "면허 없이",
        "어떻게 되나", "처벌받", "걸리면"
    ],
    # PATENT_INFRINGEMENT는 새 카테고리 — 침해품/위조품/지식재산권
    "PATENT_INFRINGEMENT": [
        "침해품", "특허 침해", "특허침해",
        "지식재산권", "지재권 침해", "지재권침해",
        "위조품", "모조품", "짝퉁",
        "상표 침해", "상표권 침해", "저작권 침해",
        "ip 침해", "ip침해",
    ],
    "CONTACT": [
        "문의", "전화", "연락처", "담당", "어디에", "누구에게",
        "상담", "고객지원", "기술지원", "보세산업과", "어디",
        "담당 부서", "소관"
    ]
}

# ---------------------------------------------------------------------------
# 카테고리 우선순위 (낮을수록 우선) — 동점 시 더 구체적인 카테고리를 선호
# ---------------------------------------------------------------------------
CATEGORY_PRIORITY = {
    "PATENT_INFRINGEMENT": 1,
    "INSPECTION": 2,
    "PATENT": 3,
    "PENALTIES": 4,
    "FOOD_TASTING": 5,
    "SAMPLE": 6,
    "SALES": 7,
    "DOCUMENTS": 8,
    "CONTACT": 9,
    "IMPORT_EXPORT": 10,
    "EXHIBITION": 11,
    "LICENSE": 12,  # PATENT의 alias로 강등
    "GENERAL": 13,
}

# 카테고리별 정확 매칭 가산점 — 정확한 phrase 매치 시 추가 점수
CATEGORY_EXACT_PHRASES = {
    "PATENT": ["특허 기간", "특허기간", "특허 신청", "특허신청", "특허 갱신",
               "특허 연장", "특허 취소"],
    "INSPECTION": ["물품 검사", "물품검사", "정기 검사", "무작위 검사",
                   "검사 절차", "검사 어떻게", "검사 진행"],
    "PATENT_INFRINGEMENT": ["침해품", "특허 침해", "특허침해",
                            "지식재산권 침해", "위조품", "모조품"],
    "FOOD_TASTING": ["시식용 식품", "시식 행사", "시식용으로"],
}

# 동의어 사전 — 정규화 단계에서 확장된다
SYNONYM_DICT = {
    "존속기간": "특허기간",
    "유효기간": "특허기간",
    "특허 면허": "특허",
    "운영 면허": "특허",
    "지재권": "지식재산권",
    "ip": "지식재산권",
    "짝퉁": "위조품",
    "모조품": "위조품",
}

# FOOD_TASTING 가드 — 다음 키워드가 있을 때만 FOOD_TASTING으로 분류 가능
FOOD_TASTING_GUARD_TOKENS = {"시식", "시식용", "식품", "음식"}


def _expand_synonyms(query_lower: str) -> str:
    """동의어 사전을 적용하여 질의를 확장한다."""
    expanded = query_lower
    for src, tgt in SYNONYM_DICT.items():
        if src in expanded:
            expanded = expanded + " " + tgt
    return expanded


def classify_query(query: str) -> list[str]:
    """사용자 질문을 카테고리로 분류한다.

    Args:
        query: 사용자 질문 문자열

    Returns:
        매칭된 카테고리 코드 리스트 (최소 1개). 매칭 없으면 ["GENERAL"].
    """
    if not query:
        return ["GENERAL"]

    query_lower = normalize_query(query)
    query_expanded = _expand_synonyms(query_lower)
    scores: dict[str, float] = {}

    for category, keywords in CATEGORY_KEYWORDS.items():
        score = 0.0
        for keyword in keywords:
            if keyword in query_expanded:
                score += 1
        # 정확 매칭 가산점
        for phrase in CATEGORY_EXACT_PHRASES.get(category, []):
            if phrase in query_expanded:
                score += 2
        if score > 0:
            scores[category] = score

    # FOOD_TASTING 가드: 시식/식품 컨텍스트 키워드가 없으면 제외
    if "FOOD_TASTING" in scores:
        if not any(tok in query_expanded for tok in FOOD_TASTING_GUARD_TOKENS):
            scores.pop("FOOD_TASTING")

    # PATENT가 매치되면 LICENSE는 제외 (중복 방지 — PATENT가 더 구체적)
    if "PATENT" in scores and "LICENSE" in scores:
        scores.pop("LICENSE")

    if not scores:
        return ["GENERAL"]

    max_score = max(scores.values())
    results = [cat for cat, sc in scores.items() if sc == max_score]

    # 도메인 우선순위로 정렬 (구체적 카테고리 우선)
    results.sort(key=lambda c: CATEGORY_PRIORITY.get(c, 99))

    return results


def get_primary_category(query: str) -> str:
    """사용자 질문의 주요 카테고리 1개를 반환한다."""
    categories = classify_query(query)
    return categories[0]


# ---------------------------------------------------------------------------
# 새 30-intent 시스템 매핑
# ---------------------------------------------------------------------------
INTENT_TO_CATEGORY_MAP = {
    "sysqual": "GENERAL",
    "license": "PATENT",
    "patent": "PATENT",

    "import_export": "IMPORT_EXPORT",
    "inspection": "INSPECTION",
    "goods_inspection": "INSPECTION",

    "exhibition": "EXHIBITION",
    "sales": "SALES",

    "sample": "SAMPLE",
    "food": "FOOD_TASTING",

    "doc": "DOCUMENTS",
    "admin": "DOCUMENTS",

    "penalty": "PENALTIES",
    "compliance": "PENALTIES",

    "patent_infringement": "PATENT_INFRINGEMENT",
    "ip": "PATENT_INFRINGEMENT",

    "support": "CONTACT",
}


# ---------------------------------------------------------------------------
# Fast-path intent 룰 — 낮은 신뢰도 환경에서도 강하게 동작
#
# 형식: (intent_id, category, [정규식 또는 phrase 리스트])
# ---------------------------------------------------------------------------
FAST_PATH_INTENTS: list[tuple[str, str, list[str]]] = [
    # 특허 침해품 (Q9) — 가장 구체적이므로 최상위
    ("patent_infringement", "PATENT_INFRINGEMENT", [
        "침해품", "특허 침해", "특허침해",
        "지식재산권 침해", "지재권 침해",
        "위조품", "모조품", "짝퉁",
        "상표 침해", "상표권 침해", "저작권 침해",
    ]),
    # 물품 검사 (Q7) — 시식 키워드 없는 단순 검사 문맥
    ("goods_inspection", "INSPECTION", [
        "물품 검사", "물품검사",
        "정기 검사", "정기검사",
        "무작위 검사", "무작위검사",
        "검사 절차", "검사절차",
        "검사 어떻게", "검사 진행", "검사 방법",
        "세관 검사", "세관검사",
        "반입 검사", "반입검사",
    ]),
    # 특허 기간 (Q1)
    ("patent_duration", "PATENT", [
        "특허 기간", "특허기간",
        "특허 존속기간", "특허 유효기간",
        "특허 몇 년", "특허 얼마",
    ]),

    # 특허 갱신/연장
    ("patent_renewal", "PATENT", [
        "특허 갱신", "특허갱신",
        "특허 연장", "특허연장",
        "특허 변경",
    ]),
    # 특허 취소
    ("patent_revocation", "PATENT", [
        "특허 취소", "특허취소",
        "특허 박탈", "특허 폐쇄",
    ]),
    # 특허 신청
    ("patent_application", "PATENT", [
        "특허 신청", "특허신청",
        "특허 수수료", "특허 받으려",
    ]),
]


def _fast_path_classify(query_lower):
    """Fast-path 룰로 질의를 분류한다 (높은 신뢰도)."""
    for intent_id, _category, phrases in FAST_PATH_INTENTS:
        for phrase in phrases:
            if phrase in query_lower:
                return (intent_id, 0.9)
    return None


def fast_path_category(query):
    """Fast-path intent 룰에 매치된 카테고리를 반환한다 (없으면 None)."""
    if not query:
        return None
    q = normalize_query(query)
    q = _expand_synonyms(q)
    for _intent_id, category, phrases in FAST_PATH_INTENTS:
        for phrase in phrases:
            if phrase in q:
                return category
    return None


class IntentClassifier:
    """새 30-intent 시스템을 지원하는 의도 분류기.

    intents.json에서 의도를 로드하고, fast-path 룰 + 키워드 매칭을 통해
    사용자 질문을 분류한다.
    """

    def __init__(self):
        self.intents = {}
        self.intent_keywords = {}
        self._load_intents()

    def _load_intents(self):
        """intents.json에서 의도 정의를 로드한다."""
        try:
            data = load_json("data/intents.json")
            if isinstance(data, list):
                intent_list = data
            else:
                intent_list = data.get("intents", [])

            for intent in intent_list:
                intent_id = intent.get("intent_id") or intent.get("id")
                if not intent_id:
                    continue
                self.intents[intent_id] = intent

                example_queries = intent.get("example_queries", [])
                keywords = set()
                for q in example_queries:
                    tokens = normalize_query(q).split()
                    keywords.update(tokens)
                description = intent.get("description", "")
                if description:
                    tokens = normalize_query(description).split()
                    keywords.update(tokens)

                self.intent_keywords[intent_id] = keywords

            logger.info(f"Loaded {len(self.intents)} intents from data/intents.json")
        except Exception as e:
            logger.warning(f"Failed to load intents.json: {e}. Graceful degradation enabled.")
            self.intents = {}
            self.intent_keywords = {}

    def classify_intent(self, query):
        """사용자 질문을 의도로 분류한다."""
        if not query:
            return ("unknown", 0.0)

        query_lower = normalize_query(query)
        query_lower = _expand_synonyms(query_lower)

        # 1) Fast-path
        fp = _fast_path_classify(query_lower)
        if fp is not None:
            return fp

        # 2) 폴백: intents.json 키워드 매칭
        if not self.intents:
            return ("unknown", 0.0)

        query_tokens = set(query_lower.split())
        best_intent = "unknown"
        best_score = 0.0

        for intent_id, keywords in self.intent_keywords.items():
            if keywords:
                matches = len(query_tokens & keywords)
                score = matches / len(keywords)
                if score > best_score:
                    best_score = score
                    best_intent = intent_id

        return (best_intent, best_score)

    def get_intent_category(self, intent_id):
        """의도 ID를 기존 카테고리 시스템으로 매핑한다."""
        if not intent_id or intent_id == "unknown":
            return "GENERAL"

        for fp_id, fp_cat, _phrases in FAST_PATH_INTENTS:
            if intent_id == fp_id:
                return fp_cat

        if intent_id in self.intents:
            intent = self.intents[intent_id]
            domain = intent.get("domain", "")
            if not domain:
                description = intent.get("description", "")
                domain = intent_id + " " + description

            if "침해" in domain or "infringement" in domain.lower() or "지재권" in domain or "지식재산" in domain:
                return "PATENT_INFRINGEMENT"
            if "물품 검사" in domain or "물품검사" in domain or "정기 검사" in domain or "검사 절차" in domain:
                return "INSPECTION"
            if "System & Qualification" in domain or "제도" in domain or "자격" in domain:
                return "GENERAL"
            if "License" in domain or "특허" in domain or "permit" in intent_id.lower():
                return "PATENT"
            # 식품/시식 우선 (tasting_food의 description에 "반입"이 들어있어
            # IMPORT_EXPORT로 잘못 매핑되는 것을 방지)
            if "Food" in domain or "식품" in domain or "시식" in domain:
                return "FOOD_TASTING"
            if "Sample" in domain or "견본" in domain:
                return "SAMPLE"
            if "Sales" in domain or "판매" in domain:
                return "SALES"
            if "Exhibition" in domain or "전시" in domain:
                return "EXHIBITION"
            if "Import" in domain or "Export" in domain or "반입" in domain or "반출" in domain:
                return "IMPORT_EXPORT"
            if "Document" in domain or "서류" in domain or "문서" in domain:
                return "DOCUMENTS"
            if "Penalty" in domain or "벌칙" in domain or "제재" in domain:
                return "PENALTIES"
            if "Support" in domain or "문의" in domain or "연락" in domain:
                return "CONTACT"

        return "GENERAL"


_intent_classifier = None


def get_intent_classifier():
    """전역 IntentClassifier 인스턴스를 반환한다 (싱글톤)."""
    global _intent_classifier
    if _intent_classifier is None:
        _intent_classifier = IntentClassifier()
    return _intent_classifier


def classify_intent(query):
    """사용자 질문을 새 30-intent 시스템으로 분류한다."""
    classifier = get_intent_classifier()
    return classifier.classify_intent(query)
