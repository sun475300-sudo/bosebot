from typing import Any
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import structlog

logger = structlog.get_logger()


class AppError(Exception):
    def __init__(self, message: str, code: str = "INTERNAL_ERROR", status_code: int = 500):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, "NOT_FOUND", 404)


class ValidationError(AppError):
    def __init__(self, message: str):
        super().__init__(message, "VALIDATION_ERROR", 422)


class AuthError(AppError):
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, "AUTH_ERROR", 401)


class RateLimitError(AppError):
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, "RATE_LIMIT", 429)


def register_exception_handlers(app: FastAPI) -> None:
    from app.models.common import APIResponse, ErrorEnvelope

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        logger.warning("app_error", code=exc.code, message=exc.message, path=str(request.url))
        return JSONResponse(
            status_code=exc.status_code,
            content=APIResponse(
                success=False,
                error=ErrorEnvelope(code=exc.code, message=exc.message),
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_error", error=str(exc), path=str(request.url))
        return JSONResponse(
            status_code=500,
            content=APIResponse(
                success=False,
                error=ErrorEnvelope(
                    code="INTERNAL_ERROR",
                    message="서버 내부 오류가 발생했습니다.",
                ),
            ).model_dump(),
        )
