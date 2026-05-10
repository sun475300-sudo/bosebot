"""TF-IDF 매칭 시그널."""

import asyncio
from typing import Any
from app.services.nlp.preprocessor import PreprocessedQuery


class TfidfSignal:
    name = "tfidf"

    def __init__(self, faq_items: list[dict[str, Any]]) -> None:
        from src.similarity import TFIDFMatcher
        self._matcher = TFIDFMatcher(faq_items)
        self._n = len(faq_items)

    async def score(
        self, pq: PreprocessedQuery, candidates: list[dict[str, Any]]
    ) -> dict[str, float]:
        return await asyncio.to_thread(self._score_sync, pq.expanded, candidates)

    def _score_sync(
        self, query: str, candidates: list[dict[str, Any]]
    ) -> dict[str, float]:
        candidate_ids = {item["id"] for item in candidates}
        results = self._matcher.find_best_match(query, top_k=self._n)
        return {
            r["item"]["id"]: r["score"]
            for r in results
            if r["item"]["id"] in candidate_ids
        }
