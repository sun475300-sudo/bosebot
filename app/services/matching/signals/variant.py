"""변형 질문 매칭 시그널."""

import asyncio
import os
from typing import Any
from app.services.nlp.preprocessor import PreprocessedQuery

_VARIANTS_PATH = "data/question_variants.json"


class VariantSignal:
    name = "variant"

    def __init__(self, faq_items: list[dict[str, Any]]) -> None:
        from src.variant_matcher import VariantMatcher
        self._matcher = VariantMatcher()
        if os.path.exists(_VARIANTS_PATH):
            try:
                self._matcher.load_variants(_VARIANTS_PATH)
            except Exception:
                pass

    async def score(
        self, pq: PreprocessedQuery, candidates: list[dict[str, Any]]
    ) -> dict[str, float]:
        return await asyncio.to_thread(self._score_sync, pq.expanded, candidates)

    def _score_sync(
        self, query: str, candidates: list[dict[str, Any]]
    ) -> dict[str, float]:
        candidate_ids = {item["id"] for item in candidates}
        hit = self._matcher.find_match(query)
        if hit and hit.get("faq_id") in candidate_ids:
            return {hit["faq_id"]: hit.get("similarity", 0.8)}
        return {}
