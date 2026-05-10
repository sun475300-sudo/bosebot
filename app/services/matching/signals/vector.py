"""벡터 신호 — sentence-transformers 기반 의미론적 매칭."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

log = logging.getLogger(__name__)


class VectorSignal:
    """VectorSearchEngine을 asyncio.to_thread로 래핑한 벡터 신호."""

    _N = 25

    def __init__(self, faq_items: list[dict[str, Any]]) -> None:
        self._available = False
        try:
            from src.vector_search import VectorSearchEngine  # type: ignore[import]

            self._engine = VectorSearchEngine(faq_items)
            self._available = True
        except Exception as exc:
            log.warning("VectorSignal unavailable — degraded gracefully: %s", exc)
            self._engine = None

    @property
    def available(self) -> bool:
        return self._available

    async def candidates(self, query: str) -> set[str]:
        if not self._available:
            return set()
        results = await asyncio.to_thread(
            self._engine.find_best_match, query, None, self._N
        )
        return {r["item"]["id"] for r in results}

    async def score(
        self, query: str, candidate_ids: set[str]
    ) -> dict[str, float]:
        if not self._available or not candidate_ids:
            return {}
        results = await asyncio.to_thread(
            self._engine.find_best_match, query, None, self._N
        )
        return {
            r["item"]["id"]: r["score"]
            for r in results
            if r["item"]["id"] in candidate_ids
        }
