"""의도 분류 및 엔티티 추출 Pydantic v2 모델."""

from pydantic import BaseModel, Field
from app.models.faq import FAQCategory


class IntentClassification(BaseModel):
    primary_category: FAQCategory = FAQCategory.UNKNOWN
    categories: list[FAQCategory] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    intent: str = ""


class EntityExtraction(BaseModel):
    user_type: str | None = None
    goods_type: str | None = None
    date_range: str | None = None
    location: str | None = None
    regulation_refs: list[str] = Field(default_factory=list)
    raw: dict = Field(default_factory=dict)
