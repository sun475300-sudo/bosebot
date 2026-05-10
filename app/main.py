from contextlib import asynccontextmanager
from typing import AsyncIterator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import router as v1_router
from app.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.middleware.request_id import RequestIDMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)

    # Load FAQ data and build retriever
    from app.repositories.faq_repo import FAQRepository
    from app.services.matching.retriever import FAQRetriever
    from app.services.nlp.preprocessor import Preprocessor
    from app.services.nlp.classifier import ClassifierService
    from app.services.nlp.entity_extractor import EntityExtractorService
    from app.services.chat_service import ChatService

    faq_repo = FAQRepository()
    await faq_repo.load()

    retriever = FAQRetriever(faq_repo.list_all())
    chat_service = ChatService(
        retriever=retriever,
        preprocessor=Preprocessor(),
        classifier=ClassifierService(),
        entity_extractor=EntityExtractorService(),
    )
    app.state.chat_service = chat_service
    app.state.faq_repo = faq_repo

    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="보세전시장 민원응대 챗봇 API",
        description="보세전시장 관련 민원을 처리하는 AI 챗봇 REST API",
        version="4.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIDMiddleware)
    register_exception_handlers(app)
    app.include_router(v1_router, prefix="/api/v1")
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.debug)
