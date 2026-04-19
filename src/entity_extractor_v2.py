"""한국어 엔티티 추출 모듈 V2.

사용자 질문에서 구조화된 엔티티 정보를 추출한다.
패턴 매칭 + data/entities.json 키워드 사전 기반.
"""

import logging
import re
from typing import Dict, List, Optional

from src.utils import load_json

logger = logging.getLogger(__name__)


class EntityExtractorV2:
    """한국어 엔티티 추출기 V2.

    data/entities.json의 엔티티 사전을 기반으로
    패턴 매칭과 키워드 매칭을 통해 구조화된 엔티티를 추출한다.
    """

    # 컨텍스트 기반 user_type 감지 패턴
    _USER_TYPE_CONTEXT_PATTERNS = {
        "신청자": [
            re.compile(r"신청(?:자|인)(?:로서|입니다|가|은|는|이|의)"),
            re.compile(r"제가\s*신청"),
            re.compile(r"신청\s*(?:하려|할|합니다)"),
        ],
        "운영사": [
            re.compile(r"(?:전시장)?운영(?:사|인|자|업체)"),
            re.compile(r"운영\s*(?:하고|하는|합니다|중)"),
        ],
        "출품업체": [
            re.compile(r"출품(?:업체|자|사|인)"),
            re.compile(r"출품\s*(?:하려|할|합니다|하는)"),
        ],
        "관세사": [
            re.compile(r"관세사"),
        ],
    }

    # 날짜 범위 패턴
    _DATE_RANGE_PATTERNS = [
        (re.compile(r"다음\s*주"), "다음주"),
        (re.compile(r"이번\s*주"), "이번주"),
        (re.compile(r"(\d+)\s*일\s*(?:후|뒤|이?내)"), None),  # 동적 값
        (re.compile(r"(\d+)\s*주\s*(?:후|뒤|이?내)"), None),
        (re.compile(r"(\d+)\s*개?월\s*(?:후|뒤|이?내)"), None),
        (re.compile(r"행사\s*기간"), "행사기간"),
        (re.compile(r"반입\s*예정일"), "반입예정일"),
        (re.compile(r"반출\s*예정일"), "반출예정일"),
        (re.compile(r"연장\s*기간"), "연장기간"),
        (re.compile(r"내일"), "내일"),
        (re.compile(r"모레"), "모레"),
        (re.compile(r"오늘"), "오늘"),
    ]

    # 신고 상태 패턴
    _DECLARATION_STATUS_PATTERNS = [
        (re.compile(r"신고\s*(?:전|이전)"), "신고전"),
        (re.compile(r"(?:반입\s*)?신고\s*완료"), "신고완료"),
        (re.compile(r"수입\s*신고\s*완료"), "수입신고완료"),
        (re.compile(r"미\s*신고"), "미신고"),
        (re.compile(r"신고(?:를|를\s*)?\s*(?:안|않|아직)"), "미신고"),
    ]

    # 법령 참조 패턴
    _LEGAL_REF_PATTERNS = [
        re.compile(r"제\s*(\d+)\s*조(?:\s*(?:의|제)?\s*(\d+))?"),
        re.compile(r"관세법"),
        re.compile(r"(?:관세법\s*)?시행[령규칙]"),
        re.compile(r"(?:대외|외국환)\s*무역법"),
        re.compile(r"수출입\s*공고"),
    ]

    def __init__(self):
        """EntityExtractorV2를 초기화한다."""
        self._entity_dict: Dict[str, List[str]] = {}
        self._entity_descriptions: Dict[str, str] = {}
        self._raw_data: list = []
        self._load_entity_dictionary()

    def _load_entity_dictionary(self):
        """data/entities.json에서 엔티티 사전을 로드한다."""
        try:
            data = load_json("data/entities.json")
            if isinstance(data, list):
                self._raw_data = data
                for entry in data:
                    entity_id = entry.get("entity_id")
                    values = entry.get("values", [])
                    description = entry.get("description", "")
                    if entity_id and values:
                        self._entity_dict[entity_id] = values
                        self._entity_descriptions[entity_id] = description
            logger.info(
                f"EntityExtractorV2: Loaded {len(self._entity_dict)} entity types"
            )
        except Exception as e:
            logger.warning(
                f"EntityExtractorV2: Failed to load entities.json: {e}. "
                "Using built-in patterns only."
            )

    def extract(self, query: str) -> List[Dict]:
        """질문에서 엔티티를 추출한다.

        Args:
            query: 사용자 질문 문자열

        Returns:
            추출된 엔티티 리스트. 각 엔티티:
            {
                "entity_type": str,
                "value": str,
                "confidence": float,
                "span": str
            }
        """
        if not query or not query.strip():
            return []

        results: List[Dict] = []

        results.extend(self._extract_user_type(query))
        results.extend(self._extract_item_type(query))
        results.extend(self._extract_action_type(query))
        results.extend(self._extract_location(query))
        results.extend(self._extract_date_range(query))
        results.extend(self._extract_declaration_status(query))
        results.extend(self._extract_legal_reference(query))

        # 중복 제거: (entity_type, value)가 같으면 confidence가 높은 것만 유지
        results = self._deduplicate(results)

        return results

    def extract_with_context(
        self, query: str, session_history: Optional[List[str]] = None
    ) -> List[Dict]:
        """대화 컨텍스트를 활용하여 엔티티를 추출한다.

        이전 대화에서 언급된 엔티티를 참조하여 현재 질문의 모호한
        엔티티를 보완한다.

        Args:
            query: 현재 사용자 질문
            session_history: 이전 대화 질문 리스트

        Returns:
            추출된 엔티티 리스트
        """
        current_entities = self.extract(query)

        if not session_history:
            return current_entities

        current_types = {e["entity_type"] for e in current_entities}

        # 이전 대화에서 엔티티 추출 (최근 3개까지)
        history_entities: List[Dict] = []
        recent_history = session_history[-3:]
        for prev_query in recent_history:
            prev_entities = self.extract(prev_query)
            history_entities.extend(prev_entities)

        # 현재 질문에 없는 타입의 엔티티를 이전 대화에서 보완
        for entity in history_entities:
            if entity["entity_type"] not in current_types:
                # 컨텍스트에서 가져온 것이므로 confidence를 낮춤
                context_entity = dict(entity)
                context_entity["confidence"] = round(
                    entity["confidence"] * 0.6, 2
                )
                context_entity["span"] = f"[컨텍스트] {entity['span']}"
                current_entities.append(context_entity)
                current_types.add(entity["entity_type"])

        return current_entities

    def get_entity_summary(self, entities: List[Dict]) -> str:
        """추출된 엔티티의 사람이 읽을 수 있는 요약을 반환한다.

        Args:
            entities: extract()가 반환한 엔티티 리스트

        Returns:
            요약 문자열
        """
        if not entities:
            return "추출된 엔티티가 없습니다."

        type_labels = {
            "user_type": "사용자 유형",
            "item_type": "물품 유형",
            "action_type": "행위",
            "location": "지역",
            "date_range": "기간",
            "declaration_status": "신고 상태",
            "legal_reference": "법령 참조",
        }

        grouped: Dict[str, List[str]] = {}
        for entity in entities:
            etype = entity["entity_type"]
            label = type_labels.get(etype, etype)
            if label not in grouped:
                grouped[label] = []
            grouped[label].append(entity["value"])

        parts = []
        for label, values in grouped.items():
            parts.append(f"{label}: {', '.join(values)}")

        return " | ".join(parts)

    def get_entity_dictionary(self) -> Dict:
        """엔티티 사전 전체를 반환한다.

        Returns:
            {entity_id: {"values": [...], "description": "..."}}
        """
        result = {}
        for entity_id, values in self._entity_dict.items():
            result[entity_id] = {
                "values": values,
                "description": self._entity_descriptions.get(entity_id, ""),
            }
        return result

    # --- 내부 추출 메서드 ---

    def _extract_user_type(self, query: str) -> List[Dict]:
        """user_type 엔티티를 추출한다."""
        results = []
        values = self._entity_dict.get("user_type", [])

        # 키워드 직접 매칭
        for value in values:
            idx = query.find(value)
            if idx != -1:
                # span을 주변 컨텍스트로 확장
                span = self._extract_span(query, idx, len(value))
                results.append({
                    "entity_type": "user_type",
                    "value": value,
                    "confidence": 0.9,
                    "span": span,
                })

        # 컨텍스트 패턴 매칭
        for canonical, patterns in self._USER_TYPE_CONTEXT_PATTERNS.items():
            # 이미 직접 매칭되었으면 건너뛰기
            if any(r["value"] == canonical for r in results):
                continue
            for pattern in patterns:
                m = pattern.search(query)
                if m:
                    results.append({
                        "entity_type": "user_type",
                        "value": canonical,
                        "confidence": 0.8,
                        "span": m.group(0),
                    })
                    break

        return results

    def _extract_item_type(self, query: str) -> List[Dict]:
        """item_type 엔티티를 추출한다."""
        results = []
        values = self._entity_dict.get("item_type", [])

        for value in values:
            idx = query.find(value)
            if idx != -1:
                span = self._extract_span(query, idx, len(value))
                results.append({
                    "entity_type": "item_type",
                    "value": value,
                    "confidence": 0.9,
                    "span": span,
                })

        # 추가 패턴: "시식용 식품" -> item_type=식품
        tasting_food_pattern = re.compile(r"시식용\s*(식품|음료)")
        m = tasting_food_pattern.search(query)
        if m and not any(r["value"] == m.group(1) for r in results):
            results.append({
                "entity_type": "item_type",
                "value": m.group(1),
                "confidence": 0.9,
                "span": m.group(0),
            })

        return results

    def _extract_action_type(self, query: str) -> List[Dict]:
        """action_type 엔티티를 추출한다."""
        results = []
        values = self._entity_dict.get("action_type", [])

        for value in values:
            # 액션 타입은 한 글자일 수 있으므로, 접미사 패턴으로 확인
            pattern = re.compile(
                re.escape(value) + r"(?:하|을|를|할|한|합니|해|했|하려|하는|시|가)?"
            )
            m = pattern.search(query)
            if m:
                span = self._extract_span(
                    query, m.start(), m.end() - m.start()
                )
                results.append({
                    "entity_type": "action_type",
                    "value": value,
                    "confidence": 0.95,
                    "span": span,
                })

        return results

    def _extract_location(self, query: str) -> List[Dict]:
        """location 엔티티를 추출한다."""
        results = []
        values = self._entity_dict.get("location", [])

        for value in values:
            # 지역명 + 세관/전시장/COEX 등 컨텍스트
            pattern = re.compile(
                re.escape(value)
                + r"(?:\s*(?:세관|본부세관|전시장|컨벤션|COEX|코엑스|BEXCO|벡스코|킨텍스|KINTEX))?"
            )
            m = pattern.search(query)
            if m:
                results.append({
                    "entity_type": "location",
                    "value": value,
                    "confidence": 0.85,
                    "span": m.group(0),
                })

        return results

    def _extract_date_range(self, query: str) -> List[Dict]:
        """date_range 엔티티를 추출한다."""
        results = []

        for pattern, static_value in self._DATE_RANGE_PATTERNS:
            m = pattern.search(query)
            if m:
                if static_value:
                    value = static_value
                else:
                    # 동적 값: "3일 후" 등
                    value = m.group(0).strip()
                results.append({
                    "entity_type": "date_range",
                    "value": value,
                    "confidence": 0.85,
                    "span": m.group(0),
                })

        return results

    def _extract_declaration_status(self, query: str) -> List[Dict]:
        """declaration_status 엔티티를 추출한다."""
        results = []

        for pattern, value in self._DECLARATION_STATUS_PATTERNS:
            m = pattern.search(query)
            if m:
                results.append({
                    "entity_type": "declaration_status",
                    "value": value,
                    "confidence": 0.9,
                    "span": m.group(0),
                })

        # entities.json의 값도 직접 매칭
        dict_values = self._entity_dict.get("declaration_status", [])
        for dv in dict_values:
            if dv in query and not any(r["value"] == dv for r in results):
                idx = query.find(dv)
                span = self._extract_span(query, idx, len(dv))
                results.append({
                    "entity_type": "declaration_status",
                    "value": dv,
                    "confidence": 0.9,
                    "span": span,
                })

        return results

    def _extract_legal_reference(self, query: str) -> List[Dict]:
        """legal_reference 엔티티를 추출한다."""
        results = []

        for pattern in self._LEGAL_REF_PATTERNS:
            for m in pattern.finditer(query):
                matched_text = m.group(0)
                results.append({
                    "entity_type": "legal_reference",
                    "value": matched_text,
                    "confidence": 0.95,
                    "span": matched_text,
                })

        return results

    # --- 유틸리티 ---

    @staticmethod
    def _extract_span(query: str, start: int, length: int, context: int = 3) -> str:
        """매칭된 위치 주변의 span을 반환한다.

        Args:
            query: 원본 질문
            start: 매칭 시작 인덱스
            length: 매칭 길이
            context: 앞뒤 추가 문자 수

        Returns:
            span 문자열
        """
        span_start = max(0, start - context)
        span_end = min(len(query), start + length + context)
        span = query[span_start:span_end].strip()
        return span

    @staticmethod
    def _deduplicate(entities: List[Dict]) -> List[Dict]:
        """(entity_type, value) 기준 중복 제거. confidence가 높은 것을 유지."""
        seen: Dict[tuple, Dict] = {}
        for entity in entities:
            key = (entity["entity_type"], entity["value"])
            if key not in seen or entity["confidence"] > seen[key]["confidence"]:
                seen[key] = entity
        return list(seen.values())


# 전역 인스턴스 (싱글톤)
_entity_extractor_v2: Optional[EntityExtractorV2] = None


def get_entity_extractor_v2() -> EntityExtractorV2:
    """전역 EntityExtractorV2 인스턴스를 반환한다."""
    global _entity_extractor_v2
    if _entity_extractor_v2 is None:
        _entity_extractor_v2 = EntityExtractorV2()
    return _entity_extractor_v2
