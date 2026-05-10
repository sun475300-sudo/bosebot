import time
from fastapi import APIRouter
from pydantic import BaseModel
from app.models.common import APIResponse

import structlog

log = structlog.get_logger(__name__)

router = APIRouter(tags=["health"])


class HealthStatus(BaseModel):
    status: str
    timestamp: float
    version: str


@router.get("/health", response_model=APIResponse[HealthStatus])
async def health_check() -> APIResponse[HealthStatus]:
    return APIResponse(
        success=True,
        data=HealthStatus(
            status="ok",
            timestamp=time.time(),
            version="4.0.0",
        ),
    )
