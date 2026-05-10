"""FAQ 매칭 결과 Pydantic v2 모델."""

from typing import Literal
from pydantic import BaseModel, Field
from app.models.faq import FAQCategory


class SignalContribution(BaseModel):
    raw: float
    normalized: float = Field(ge=0.0, le=1.0)
    weight: float = Field(ge=0.0, le=1.0)
    weighted: float = Field(ge=0.0, le=1.0)


class FAQSearchHit(BaseModel):
    faq_id: str
    question: str
    answer: str
    category: FAQCategory
    score: float = Field(ge=0.0, le=1.0)
    legal_basis: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class MatchExplanation(BaseModel):
    final_score: float = Field(ge=0.0, le=1.0)
    fusion_strategy: Literal["weighted_sum", "rrf", "hybrid"] = "weighted_sum"
    signal_scores: dict[str, SignalContribution] = Field(default_factory=dict)
    candidate_pool_size: int = 0
    category_filter: str | None = None
    confidence_band: Literal["high", "medium", "low"] = "low"
    chosen_via: Literal["exact_alias", "ensemble", "llm_fallback"] = "ensemble"
