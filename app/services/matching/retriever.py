"""FAQ 앙상블 Retriever — 핵심 매칭 엔진.

파이프라인:
  1. 전처리 (preprocessor)
  2. 모든 신호에서 후보 생성 (union)
  3. 신호별 점수 계산
  4. 정규화 + 융합 (WeightedSum 기본)
  5. Confidence 게이팅
  6. MatchExplanation 생성
"""

from __future__ import annotations

import asyncio
import math
from typing import Any, Literal

from app.models.matching import MatchExplanation, SignalContribution, FAQSearchHit
from app.models.faq import FAQCategory
from app.services.matching.fusion import WeightedSumFusion, RRFFusion
from app.services.matching.signals.keyword import KeywordSignal
from app.services.matching.signals.tfidf import TfidfSignal
from app.services.matching.signals.bm25 import Bm25Signal
from app.services.matching.signals.variant import VariantSignal
from app.services.matching.signals.vector import VectorSignal
from app.services.nlp.preprocessor import PreprocessedQuery

import structlog

log = structlog.get_logger(__name__)

HIGH_CONFIDENCE = 0.55
MEDIUM_CONFIDENCE = 0.35


class FAQRetriever:
    """앙상블 신호 융합 기반 FAQ 검색 엔진."""

    def __init__(
        self,
        faq_items: list[dict[str, Any]],
        fusion_strategy: Literal["weighted_sum", "rrf", "hybrid"] = "weighted_sum",
    ) -> None:
        self._items = faq_items
        self._by_id: dict[str, dict[str, Any]] = {item["id"]: item for item in faq_items}
        self._strategy = fusion_strategy

        # 신호 초기화 (CPU-bound 빌드는 __init__에서 동기 실행)
        self._keyword = KeywordSignal(faq_items)
        self._tfidf = TfidfSignal(faq_items)
        self._bm25 = Bm25Signal(faq_items)
        self._variant = VariantSignal(faq_items)
        self._vector = VectorSignal(faq_items)

        self._weighted_fusion = WeightedSumFusion()
        self._rrf_fusion = RRFFusion()

        # 별칭 매핑 (정확한 별칭 → hard-lock)
        self._aliases: dict[str, str] = self._build_aliases(faq_items)

    @staticmethod
    def _build_aliases(items: list[dict[str, Any]]) -> dict[str, str]:
        aliases: dict[str, str] = {}
        for item in items:
            q = item.get("question", "").strip()
            if q:
                aliases[q] = item["id"]
        return aliases

    async def retrieve(
        self,
        pq: PreprocessedQuery,
        category_filter: str | None = None,
        category_confidence: float = 0.0,
        top_k: int = 1,
    ) -> tuple[list[FAQSearchHit], MatchExplanation]:
        """앙상블 매칭을 수행하고 상위 K개 + 설명을 반환한다."""

        # 정확한 별칭 매치 → hard-lock
        for q, faq_id in self._aliases.items():
            if pq.original.strip() == q or pq.expanded.strip() == q:
                item = self._by_id[faq_id]
                hit = self._make_hit(item, 1.0)
                explain = MatchExplanation(
                    final_score=1.0,
                    fusion_strategy="weighted_sum",
                    confidence_band="high",
                    chosen_via="exact_alias",
                    candidate_pool_size=1,
                    category_filter=category_filter,
                )
                return [hit], explain

        # 변형 질문 고신뢰도 매치 → hard-lock (variant score ≥ 0.92)
        variant_hit = await asyncio.to_thread(
            self._variant._matcher.find_match, pq.original.strip()
        )
        if variant_hit is None:
            variant_hit = await asyncio.to_thread(
                self._variant._matcher.find_match, pq.expanded.strip()
            )
        if variant_hit and variant_hit.get("score", 0.0) >= 0.92:
            faq_id = variant_hit["faq_id"]
            item = self._by_id.get(faq_id)
            if item:
                score = min(1.0, variant_hit["score"])
                hit = self._make_hit(item, score)
                explain = MatchExplanation(
                    final_score=score,
                    fusion_strategy="weighted_sum",
                    confidence_band="high",
                    chosen_via="exact_alias",
                    candidate_pool_size=1,
                    category_filter=category_filter,
                )
                return [hit], explain

        # 후보 생성 (전체 FAQ 대상)
        candidates = self._items

        # 시그널별 점수 계산 (병렬)
        candidate_ids = {item["id"] for item in candidates}
        all_scores_list = await asyncio.gather(
            self._keyword.score(pq, candidates),
            self._tfidf.score(pq, candidates),
            self._bm25.score(pq, candidates),
            self._variant.score(pq, candidates),
            self._vector.score(pq.expanded, candidate_ids),
        )
        all_scores: dict[str, dict[str, float]] = {
            "keyword": all_scores_list[0],
            "tfidf": all_scores_list[1],
            "bm25": all_scores_list[2],
            "variant": all_scores_list[3],
            "vector": all_scores_list[4],
        }

        # 융합
        if self._strategy == "rrf":
            final_scores = self._rrf_fusion.fuse(
                all_scores, candidates, category_filter, category_confidence
            )
        elif self._strategy == "hybrid":
            ws = self._weighted_fusion.fuse(
                all_scores, candidates, category_filter, category_confidence
            )
            rrf = self._rrf_fusion.fuse(
                all_scores, candidates, category_filter, category_confidence
            )
            # top-1 vs top-2 margin 체크 후 tiebreak로 RRF 사용
            if ws:
                top2 = sorted(ws.values(), reverse=True)[:2]
                margin = top2[0] - (top2[1] if len(top2) > 1 else 0.0)
                if margin < 0.05 and top2[0] < HIGH_CONFIDENCE:
                    final_scores = rrf
                else:
                    final_scores = ws
            else:
                final_scores = rrf
        else:
            final_scores = self._weighted_fusion.fuse(
                all_scores, candidates, category_filter, category_confidence
            )

        # 정렬 및 상위 K개 선택
        ranked = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)
        top_items = ranked[:top_k]

        hits = []
        for faq_id, score in top_items:
            item = self._by_id.get(faq_id)
            if item:
                hits.append(self._make_hit(item, min(1.0, max(0.0, score))))

        # Confidence band 결정
        top_score = top_items[0][1] if top_items else 0.0
        top2_scores = [s for _, s in ranked[:2]]
        margin = (top2_scores[0] - top2_scores[1]) if len(top2_scores) > 1 else 1.0

        if top_score >= HIGH_CONFIDENCE:
            band: Literal["high", "medium", "low"] = "high"
        elif top_score >= MEDIUM_CONFIDENCE:
            band = "medium"
        else:
            band = "low"
        if margin < 0.05 and top_score < HIGH_CONFIDENCE:
            band = "medium"

        # 신호 기여도 빌드 (설명용)
        weights = self._weighted_fusion._weights
        signal_contribs: dict[str, SignalContribution] = {}
        for sig_name, raw_scores in all_scores.items():
            if top_items:
                top_faq_id = top_items[0][0]
                raw = raw_scores.get(top_faq_id, 0.0)
                w = weights.get(sig_name, 0.0)
                signal_contribs[sig_name] = SignalContribution(
                    raw=raw,
                    normalized=min(1.0, max(0.0, raw)),
                    weight=w,
                    weighted=min(1.0, w * raw),
                )

        explain = MatchExplanation(
            final_score=min(1.0, max(0.0, top_score)),
            fusion_strategy=self._strategy if self._strategy != "hybrid" else "hybrid",
            signal_scores=signal_contribs,
            candidate_pool_size=len(candidates),
            category_filter=category_filter,
            confidence_band=band,
            chosen_via="ensemble",
        )

        return hits, explain

    def _make_hit(self, item: dict[str, Any], score: float) -> FAQSearchHit:
        try:
            cat = FAQCategory(item.get("category", "UNKNOWN"))
        except ValueError:
            cat = FAQCategory.UNKNOWN
        return FAQSearchHit(
            faq_id=item["id"],
            question=item.get("question", ""),
            answer=item.get("answer", ""),
            category=cat,
            score=score,
            legal_basis=item.get("legal_basis", []),
            keywords=item.get("keywords", []),
        )
