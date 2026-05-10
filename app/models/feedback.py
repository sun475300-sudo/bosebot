"""피드백 Pydantic v2 모델."""

from typing import Literal
from pydantic import BaseModel, Field


class FeedbackRequest(BaseModel):
    query_id: str = Field(min_length=1, max_length=64)
    rating: Literal["helpful", "unhelpful"]
    comment: str = Field(default="", max_length=500)


class FeedbackResponse(BaseModel):
    feedback_id: int
    message: str
