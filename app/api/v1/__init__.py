from fastapi import APIRouter
from app.api.v1 import health, chat, feedback
from app.api.v1.admin import router as admin_router

router = APIRouter()
router.include_router(health.router)
router.include_router(chat.router)
router.include_router(feedback.router)
router.include_router(admin_router)
