"""채팅 오케스트레이터 서비스.

파이프라인:
  1. 전처리 (Preprocessor)
  2. 의도 분류 (ClassifierService)
  3. 엔티티 추출 (EntityExtractorService)
  4. 에스컬레이션 확인 (src/escalation.py)
  5. FAQ 앙상블 검색 (FAQRetriever)
  6. 응답 구성 (ResponseBuilderV2)
  7. ChatResponse 반환
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

from app.models.chat import ChatRequest, ChatResponse, EscalationDecision
from app.models.intent import IntentClassification, EntityExtraction
from app.models.matching import FAQSearchHit, MatchExplanation
from app.models.faq import FAQCategory
from app.services.nlp.preprocessor import Preprocessor
from app.services.nlp.classifier import ClassifierService
from app.services.nlp.entity_extractor import EntityExtractorService
from app.services.matching.retriever import FAQRetriever, MEDIUM_CONFIDENCE


class ChatService:
    """채팅 요청 처리 메인 오케스트레이터."""

    def __init__(
        self,
        retriever: FAQRetriever,
        preprocessor: Preprocessor | None = None,
        classifier: ClassifierService | None = None,
        entity_extractor: EntityExtractorService | None = None,
    ) -> None:
        self._retriever = retriever
        self._preprocessor = preprocessor or Preprocessor()
        self._classifier = classifier or ClassifierService()
        self._extractor = entity_extractor or EntityExtractorService()
        self._response_builder = self._init_response_builder()

    @staticmethod
    def _init_response_builder():
        from src.response_builder_v2 import get_response_builder_v2
        return get_response_builder_v2()

    async def process(self, req: ChatRequest, request_id: str = "") -> ChatResponse:
        start = time.monotonic()
        if not request_id:
            request_id = str(uuid.uuid4())

        # 1. 전처리
        pq = await self._preprocessor.process(req.query)

        # 2+3. 분류 + 엔티티 (병렬)
        intent, entities = await asyncio.gather(
            self._classifier.classify(pq),
            self._extractor.extract(pq),
        )

        # 4. 에스컬레이션 확인
        escalation = await asyncio.to_thread(self._check_escalation, pq.expanded)

        # 5. FAQ 앙상블 검색
        category_filter = (
            intent.primary_category.value
            if intent.primary_category != FAQCategory.UNKNOWN
            else None
        )
        hits, explain = await self._retriever.retrieve(
            pq,
            category_filter=category_filter,
            category_confidence=intent.confidence,
            top_k=3,
        )

        # 6. 응답 구성
        top_hit = hits[0] if hits else None
        response_text = await asyncio.to_thread(
            self._compose_response, top_hit, escalation, explain
        )

        latency_ms = int((time.monotonic() - start) * 1000)
        return ChatResponse(
            response=response_text,
            intent=intent,
            entities=entities,
            matched_faq=top_hit,
            escalation=escalation,
            explain=explain if req.include_metadata else None,
            request_id=request_id,
            latency_ms=latency_ms,
        )

    @staticmethod
    def _check_escalation(query: str) -> EscalationDecision:
        from src.escalation import check_escalation, get_escalation_contact
        rule = check_escalation(query)
        if not rule:
            return EscalationDecision()
        contact_info = get_escalation_contact(rule)
        return EscalationDecision(
            should_escalate=True,
            rule_id=rule.get("id"),
            contact=contact_info.get("phone") or contact_info.get("name"),
            reason=rule.get("description"),
        )

    def _compose_response(
        self,
        hit: FAQSearchHit | None,
        escalation: EscalationDecision,
        explain: MatchExplanation,
    ) -> str:
        if escalation.should_escalate and not hit:
            return (
                f"이 질문은 담당자 상담이 필요합니다. "
                f"연락처: {escalation.contact or '관할 세관'}"
            )

        faq_item: dict[str, Any] | None = None
        if hit:
            faq_item = {
                "id": hit.faq_id,
                "question": hit.question,
                "answer": hit.answer,
                "legal_basis": hit.legal_basis,
                "keywords": hit.keywords,
                "category": hit.category.value,
            }

        if hit is None or explain.confidence_band == "low":
            result = self._response_builder.build_unknown("")
        else:
            result = self._response_builder.build(faq_item)

        # format_plain returns the text representation
        try:
            return self._response_builder.format_plain(result)
        except Exception:
            return result.get("summary", "답변을 찾지 못했습니다.")
