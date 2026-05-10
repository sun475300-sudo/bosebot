"""피드백 API 엔드포인트."""

from fastapi import APIRouter
from app.models.feedback import FeedbackRequest, FeedbackResponse
from app.models.common import APIResponse

router = APIRouter(tags=["feedback"])


@router.post("/feedback", response_model=APIResponse[FeedbackResponse])
async def submit_feedback(req: FeedbackRequest) -> APIResponse[FeedbackResponse]:
    # Phase 1의 FeedbackRepository는 lifespan에서 연결 필요 (Phase 5에서 완성)
    return APIResponse(
        success=True,
        data=FeedbackResponse(feedback_id=0, message="피드백이 접수되었습니다."),
    )
