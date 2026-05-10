from typing import Any, Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class ErrorEnvelope(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class APIResponse(BaseModel, Generic[T]):
    success: bool
    data: T | None = None
    error: ErrorEnvelope | None = None
    meta: dict[str, Any] | None = None


class PaginatedMeta(BaseModel):
    total: int
    page: int
    limit: int
    has_next: bool
