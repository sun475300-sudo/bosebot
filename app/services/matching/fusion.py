"""점수 융합 전략.

WeightedSumFusion: 가중 합산 (기본)
RRFFusion: Reciprocal Rank Fusion (강건한 대안)
"""

from __future__ import annotations
import math
from typing import Any

import structlog

log = structlog.get_logger(__name__)


def _minmax_normalize(scores: dict[str, float]) -> dict[str, float]:
    """값을 [0,1] 범위로 min-max 정규화한다."""
    if not scores:
        return {}
    mn = min(scores.values())
    mx = max(scores.values())
    if mx == mn:
        return {k: 0.5 for k in scores}
    return {k: (v - mn) / (mx - mn) for k, v in scores.items()}


def _sigmoid_normalize(scores: dict[str, float]) -> dict[str, float]:
    """z-score → sigmoid 변환으로 무경계 점수를 [0,1]에 매핑한다."""
    if not scores:
        return {}
    vals = list(scores.values())
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / len(vals)
    std = math.sqrt(var) if var > 0 else 1.0
    return {k: 1 / (1 + math.exp(-((v - mean) / std))) for k, v in scores.items()}


class WeightedSumFusion:
    """정규화된 점수의 가중 합산."""

    DEFAULT_WEIGHTS: dict[str, float] = {
        "keyword": 0.15,
        "tfidf": 0.20,
        "bm25": 0.25,
        "variant": 0.15,
        "vector": 0.25,
    }

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self._weights = weights or dict(self.DEFAULT_WEIGHTS)

    def fuse(
        self,
        all_scores: dict[str, dict[str, float]],
        candidates: list[dict[str, Any]],
        category_filter: str | None = None,
        category_confidence: float = 0.0,
    ) -> dict[str, float]:
        """시그널별 점수를 정규화 후 가중 합산한다."""
        normalized: dict[str, dict[str, float]] = {}
        for signal_name, scores in all_scores.items():
            if signal_name in ("keyword",):
                normalized[signal_name] = _sigmoid_normalize(scores)
            elif signal_name == "bm25":
                normalized[signal_name] = _sigmoid_normalize(scores)
            else:
                normalized[signal_name] = _minmax_normalize(scores)

        all_ids = {item["id"] for item in candidates}
        final: dict[str, float] = {}
        for faq_id in all_ids:
            total_weight = 0.0
            score_sum = 0.0
            for signal_name, norm_scores in normalized.items():
                w = self._weights.get(signal_name, 0.0)
                s = norm_scores.get(faq_id, 0.0)
                score_sum += w * s
                total_weight += w
            final[faq_id] = score_sum / total_weight if total_weight > 0 else 0.0

            # 카테고리 보너스 (classifier confidence ≥ 0.7)
            if category_filter and category_confidence >= 0.7:
                item = next((c for c in candidates if c["id"] == faq_id), None)
                if item and item.get("category") == category_filter:
                    final[faq_id] = min(1.0, final[faq_id] * 1.05)

        return final


class RRFFusion:
    """Reciprocal Rank Fusion (k=60) — 점수 스케일에 무관한 융합."""

    def __init__(self, k: int = 60) -> None:
        self._k = k

    def fuse(
        self,
        all_scores: dict[str, dict[str, float]],
        candidates: list[dict[str, Any]],
        category_filter: str | None = None,
        category_confidence: float = 0.0,
    ) -> dict[str, float]:
        rrf: dict[str, float] = {}
        for scores in all_scores.values():
            ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            for rank, (faq_id, _) in enumerate(ranked, start=1):
                rrf[faq_id] = rrf.get(faq_id, 0.0) + 1.0 / (self._k + rank)

        # 정규화
        if rrf:
            mx = max(rrf.values())
            if mx > 0:
                rrf = {k: v / mx for k, v in rrf.items()}

        # 카테고리 보너스
        if category_filter and category_confidence >= 0.7:
            for item in candidates:
                if item.get("category") == category_filter and item["id"] in rrf:
                    rrf[item["id"]] = min(1.0, rrf[item["id"]] * 1.05)

        return rrf
