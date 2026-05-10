"""매칭 가중치 관리 Admin API."""

from fastapi import APIRouter, Request
from pydantic import BaseModel
from app.models.common import APIResponse

router = APIRouter(prefix="/admin", tags=["admin"])


class WeightUpdate(BaseModel):
    keyword: float = 0.15
    tfidf: float = 0.20
    bm25: float = 0.25
    variant: float = 0.15
    vector: float = 0.25


@router.post("/matching/reload-weights", response_model=APIResponse[dict])
async def reload_weights(request: Request) -> APIResponse[dict]:
    """config/matching.yaml 에서 가중치를 재로드한다."""
    try:
        import yaml
        with open("config/matching.yaml", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        weights = cfg.get("weights", {})
        chat_service = request.app.state.chat_service
        chat_service._retriever._weighted_fusion._weights = weights
        return APIResponse(success=True, data={"weights": weights})
    except Exception as e:
        return APIResponse(success=False, data={"error": str(e)})


@router.get("/matching/explain", response_model=APIResponse[dict])
async def explain_matching(query: str, request: Request) -> APIResponse[dict]:
    """질문에 대한 매칭 설명을 반환한다."""
    from app.services.nlp.preprocessor import Preprocessor
    prep = Preprocessor()
    pq = await prep.process(query)
    chat_service = request.app.state.chat_service
    hits, explain = await chat_service._retriever.retrieve(pq, top_k=3)
    return APIResponse(
        success=True,
        data={
            "query": query,
            "preprocessed": pq.expanded,
            "top_matches": [{"faq_id": h.faq_id, "score": h.score, "question": h.question} for h in hits],
            "explanation": explain.model_dump(),
        },
    )
