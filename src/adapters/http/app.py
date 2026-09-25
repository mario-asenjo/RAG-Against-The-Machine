"""FastAPI application factory for the local bonus adapter."""

from __future__ import annotations

from fastapi import FastAPI

from src.adapters.http.errors import register_error_handlers
from src.adapters.http.routers import (
    answer_router,
    index_router,
    search_router,
)
from src.application.use_cases import RagApplication
from src.infrastructure.pipeline import LocalPipelineOperations


def create_app(application: RagApplication | None = None) -> FastAPI:
    """Create a local FastAPI app around the shared application seam."""
    app = FastAPI(
        title="RAG Against the Machine local API",
        description=(
            "Local synchronous bonus adapter. No authentication, idempotency, "
            "thread-safety, job queue, or remote-deployment guarantee."
        ),
        version="1.0.0",
    )
    app.state.rag_application = application or RagApplication(
        LocalPipelineOperations()
    )
    register_error_handlers(app)
    app.include_router(index_router)
    app.include_router(search_router)
    app.include_router(answer_router)
    return app
