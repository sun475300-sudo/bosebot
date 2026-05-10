"""엔티티 추출 서비스 — EntityExtractorV2 비동기 래퍼."""

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
        raw = await asyncio.to_thread(
            self._get_extractor().extract_entities, pq.expanded
        )
        return EntityExtraction(
            user_type=raw.get("user_type"),
            goods_type=raw.get("goods_type"),
            date_range=raw.get("date_range"),
            location=raw.get("location"),
            regulation_refs=raw.get("regulation_refs", []),
            raw=raw,
        )
