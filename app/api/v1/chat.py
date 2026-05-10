"""채팅 API 엔드포인트."""

import uuid
from fastapi import APIRouter, Request
from app.models.chat import ChatRequest, ChatResponse
from app.models.common import APIResponse

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=APIResponse[ChatResponse])
async def chat(req_body: ChatRequest, request: Request) -> APIResponse[ChatResponse]:
    chat_service = request.app.state.chat_service
    request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
    result = await chat_service.process(req_body, request_id=request_id)
    return APIResponse(success=True, data=result)
