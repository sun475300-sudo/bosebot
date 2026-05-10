from fastapi import APIRouter
from app.api.v1.admin import faq, matching, stats

router = APIRouter()
router.include_router(faq.router)
router.include_router(matching.router)
router.include_router(stats.router)
