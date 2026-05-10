from fastapi import APIRouter
from app.api.v1 import health, chat, feedback

router = APIRouter()
router.include_router(health.router)
router.include_router(chat.router)
router.include_router(feedback.router)
