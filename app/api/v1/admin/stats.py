"""통계 Admin API."""

from fastapi import APIRouter
from app.models.common import APIResponse

import structlog

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats", response_model=APIResponse[dict])
async def get_stats() -> APIResponse[dict]:
    """기본 통계 (Phase 5에서 DB 연결 완성)."""
    return APIResponse(
        success=True,
        data={"message": "Phase 5에서 DB 연결 완성 예정"},
    )
