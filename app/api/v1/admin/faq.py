"""FAQ 관리 Admin API."""

from fastapi import APIRouter, Request
from app.models.common import APIResponse
from app.models.faq import FAQItem

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/faq", response_model=APIResponse[list[dict]])
async def list_faq(request: Request) -> APIResponse[list[dict]]:
    faq_repo = request.app.state.faq_repo
    return APIResponse(success=True, data=faq_repo.list_all())


@router.get("/faq/{faq_id}", response_model=APIResponse[dict])
async def get_faq(faq_id: str, request: Request) -> APIResponse[dict]:
    faq_repo = request.app.state.faq_repo
    item = faq_repo.get_by_id(faq_id)
    if not item:
        return APIResponse(success=False, data=None)
    return APIResponse(success=True, data=item)


@router.post("/faq/reload", response_model=APIResponse[dict])
async def reload_faq(request: Request) -> APIResponse[dict]:
    """FAQ 파일을 재로드하고 매처 인덱스를 갱신한다."""
    faq_repo = request.app.state.faq_repo
    await faq_repo.reload()
    # 리트리버도 갱신
    from app.services.matching.retriever import FAQRetriever
    new_retriever = FAQRetriever(faq_repo.list_all())
    chat_service = request.app.state.chat_service
    chat_service._retriever = new_retriever
    return APIResponse(
        success=True,
        data={"version": faq_repo.version, "count": faq_repo.count, "hash": faq_repo.corpus_hash},
    )
