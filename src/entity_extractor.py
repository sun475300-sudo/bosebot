"""엔티티 추출 모듈.

사용자 질문에서 의미 있는 엔티티(사용자 유형, 행사 유형, 지역, 물품 등)를 추출한다.
"""

import logging
import re
from typing import Optional
from src.utils import normalize_query, load_json

logger = logging.getLogger(__name__)


class EntityExtractor:
    """엔티티 추출기."""

    def __init__(self):
        """EntityExtractor를 초기화한다."""
        self.entity_types = {}
        self.extraction_patterns = {}
        self._load_entity_definitions()

    def _load_entity_definitions(self):
        """data/entities.json에서 엔티티 정의를 로드한다."""
        try:
            data = load_json("data/entities.json")
            # entities.json은 list 또는 dict({'entity_types': [...]}) 형식을 모두 지원
            if isinstance(data, list):
                entity_types = data
            else:
                entity_types = data.get("entity_types", [])

            for entity_type in entity_types:
                # 'entity_id' 키를 우선 사용하고, 없으면 'id' 키를 사용
                entity_id = entity_type.get("entity_id") or entity_type.get("id")
                if not entity_id:
                    continue
                self.entity_types[entity_id] = entity_type

                # 추출 패턴 컴파일
                patterns = entity_type.get("extraction_patterns", [])
                if patterns:
                    # 패턴들을 OR로 결합
                    combined_pattern = "|".join(f"({p})" for p in patterns)
                    try:
                        self.extraction_patterns[entity_id] = re.compile(
                            combined_pattern, re.IGNORECASE
                        )
                    except re.error as e:
                        logger.warning(f"Failed to compile pattern for {entity_id}: {e}")

            logger.info(f"Loaded {len(self.entity_types)} entity types from data/entities.json")
        except Exception as e:
            logger.warning(f"Failed to load entities.json: {e}. Graceful degradation enabled.")
            self.entity_types = {}
            self.extraction_patterns = {}

    def extract(self, query: str) -> dict:
        """질문에서 엔티티를 추출한다.

        Args:
            query: 사용자 질문 문자열

        Returns:
            {
                "entity_type_id": [
                    {
                        "value": "extracted_value",
                        "synonyms": ["synonym1", "synonym2"],
                        "confidence": 0.8
                    },
                    ...
                ],
                ...
            }
        """
        if not query or not self.entity_types:
            return {}

        extracted_entities = {}

        for entity_id, entity_type in self.entity_types.items():
            matched_entities = []

            # 패턴 기반 추출
            if entity_id in self.extraction_patterns:
                pattern = self.extraction_patterns[entity_id]
                matches = pattern.finditer(query, re.IGNORECASE)
                for match in matches:
                    matched_text = match.group(0)
                    matched_entities.append({
                        "value": matched_text.lower(),
                        "matched_text": matched_text,
                        "confidence": 0.9,
                    })

            # 엔티티 값과 동의어 확인
            values = entity_type.get("values", [])
            for value_obj in values:
                # values는 string 또는 dict({'value': ..., 'synonyms': [...]}) 형식 모두 지원
                if isinstance(value_obj, str):
                    value = value_obj
                    synonyms = []
                else:
                    value = value_obj.get("value")
                    synonyms = value_obj.get("synonyms", [])

                if not value:
                    continue

                # 정확한 값 매칭
                if value.lower() in normalize_query(query):
                    matched_entities.append({
                        "value": value,
                        "matched_text": value,
                        "confidence": 0.95,
                    })

                # 동의어 매칭
                for synonym in synonyms:
                    if synonym.lower() in normalize_query(query):
                        matched_entities.append({
                            "value": value,
                            "matched_text": synonym,
                            "confidence": 0.85,
                        })

            if matched_entities:
                # 중복 제거 (동일한 value 유지)
                seen = set()
                unique_entities = []
                for entity in matched_entities:
                    key = entity["value"]
                    if key not in seen:
                        seen.add(key)
                        unique_entities.append(entity)

                extracted_entities[entity_id] = unique_entities

        return extracted_entities

    def get_entity_value_description(self, entity_id: str, value: str) -> Optional[str]:
        """엔티티 값의 설명을 반환한다.

        Args:
            entity_id: 엔티티 타입 ID
            value: 엔티티 값

        Returns:
            설명 문자열 또는 None
        """
        if entity_id not in self.entity_types:
            return None

        entity_type = self.entity_types[entity_id]
        values = entity_type.get("values", [])

        for value_obj in values:
            # values는 string 또는 dict({'value': ..., 'description': ...}) 형식 모두 지원
            if isinstance(value_obj, str):
                if value_obj == value:
                    # string 형식에는 description이 없음
                    return None
            else:
                if value_obj.get("value") == value:
                    return value_obj.get("description")

        return None


# 전역 EntityExtractor 인스턴스
_entity_extractor: Optional[EntityExtractor] = None


def get_entity_extractor() -> EntityExtractor:
    """전역 EntityExtractor 인스턴스를 반환한다 (싱글톤)."""
    global _entity_extractor
    if _entity_extractor is None:
        _entity_extractor = EntityExtractor()
    return _entity_extractor


def extract_entities(query: str) -> dict:
    """질문에서 엔티티를 추출한다.

    Args:
        query: 사용자 질문 문자열

    Returns:
        추출된 엔티티 딕셔너리
    """
    extractor = get_entity_extractor()
    return extractor.extract(query)
