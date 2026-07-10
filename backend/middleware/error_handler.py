"""
middleware/error_handler.py — Exception handling middleware mapping AppException to HTTP JSONResponse.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.exceptions import AppException


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Catches AppException and returns the matching HTTP response."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )


def register_error_handlers(app: FastAPI):
    """Registers exception handlers on the FastAPI app instance."""
    app.add_exception_handler(AppException, app_exception_handler)
