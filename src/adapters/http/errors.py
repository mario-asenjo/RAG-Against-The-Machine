"""Expected application-to-HTTP error translation."""

from __future__ import annotations

import sqlite3
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.adapters.http.models import ApiError


def _response(status_code: int, error: Exception) -> JSONResponse:
    """Build one stable Pydantic-owned error response."""
    return JSONResponse(
        status_code=status_code,
        content=ApiError(error=str(error)).model_dump(),
    )


async def not_found_error(
    request: Request,
    error: Exception,
) -> JSONResponse:
    """Map a missing local artifact to HTTP 404."""
    del request
    return _response(404, error)


async def invalid_request_error(
    request: Request,
    error: Exception,
) -> JSONResponse:
    """Map valid JSON with invalid operation semantics to HTTP 400."""
    del request
    return _response(400, error)


async def technical_error(
    request: Request,
    error: Exception,
) -> JSONResponse:
    """Map expected local runtime failures without returning a traceback."""
    del request
    return _response(500, error)


def register_error_handlers(app: FastAPI) -> None:
    """Install only the expected local pipeline error mappings."""
    app.add_exception_handler(FileNotFoundError, not_found_error)
    app.add_exception_handler(ValueError, invalid_request_error)
    app.add_exception_handler(RuntimeError, technical_error)
    app.add_exception_handler(OSError, technical_error)
    app.add_exception_handler(sqlite3.Error, technical_error)
