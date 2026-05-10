"""키워드 매칭 시그널."""

import asyncio
from typing import Any
from app.services.nlp.preprocessor import PreprocessedQuery


class KeywordSignal:
    name = "keyword"

    def __init__(self, faq_items: list[dict[str, Any]]) -> None:
        self._items = faq_items

    async def score(
        self, pq: PreprocessedQuery, candidates: list[dict[str, Any]]
    ) -> dict[str, float]:
        return await asyncio.to_thread(self._score_sync, pq.expanded, candidates)

    def _score_sync(
        self, query: str, candidates: list[dict[str, Any]]
    ) -> dict[str, float]:
        from src.utils import normalize_query
        tokens = set(normalize_query(query).split())
        scores: dict[str, float] = {}
        for item in candidates:
            kw_hits = sum(1 for kw in item.get("keywords", []) if kw in tokens)
            q_hits = sum(1 for t in tokens if t in normalize_query(item.get("question", "")))
            scores[item["id"]] = float(kw_hits + q_hits)
        return scores
