"""엔티티 추출 서비스 — EntityExtractorV2 비동기 래퍼.

EntityExtractorV2.extract(query) -> List[Dict]
각 Dict: {type, value, span, context, ...}
"""

import asyncio
from app.models.intent import EntityExtraction
from app.services.nlp.preprocessor import PreprocessedQuery


class EntityExtractorService:
    def __init__(self) -> None:
        self._extractor = None

    def _get_extractor(self):
        if self._extractor is None:
            from src.entity_extractor_v2 import EntityExtractorV2
            self._extractor = EntityExtractorV2()
        return self._extractor

    async def extract(self, pq: PreprocessedQuery) -> EntityExtraction:
        raw_list = await asyncio.to_thread(
            self._get_extractor().extract, pq.expanded
        )
        return self._parse(raw_list)

    @staticmethod
    def _parse(entities: list[dict]) -> EntityExtraction:
        user_type = None
        goods_type = None
        date_range = None
        location = None
        regulation_refs: list[str] = []

        for ent in entities:
            etype = ent.get("type", "")
            value = ent.get("value", "")
            if etype == "user_type" and not user_type:
                user_type = value
            elif etype == "item_type" and not goods_type:
                goods_type = value
            elif etype == "date_range" and not date_range:
                date_range = value
            elif etype == "location" and not location:
                location = value
            elif etype == "legal_reference":
                regulation_refs.append(value)

        return EntityExtraction(
            user_type=user_type,
            goods_type=goods_type,
            date_range=date_range,
            location=location,
            regulation_refs=regulation_refs,
            raw={"entities": entities},
        )
