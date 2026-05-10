"""채팅 요청/응답 Pydantic v2 모델."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from app.models.faq import FAQCategory
from app.models.intent import IntentClassification, EntityExtraction
from app.models.matching import FAQSearchHit, MatchExplanation


class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(min_length=1, max_length=500)
    session_id: str | None = Field(
        default=None, pattern=r"^[a-zA-Z0-9_-]{8,64}$"
    )
    locale: Literal["ko", "en", "jp", "cn", "vi", "th"] = "ko"
    include_metadata: bool = False
    tenant_id: str | None = None


class EscalationDecision(BaseModel):
    should_escalate: bool = False
    rule_id: str | None = None
    contact: str | None = None
    reason: str | None = None


class ChatResponse(BaseModel):
    response: str
    intent: IntentClassification
    entities: EntityExtraction
    matched_faq: FAQSearchHit | None = None
    escalation: EscalationDecision
    explain: MatchExplanation | None = None
    request_id: str = ""
    latency_ms: int = 0
