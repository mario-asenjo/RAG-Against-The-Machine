"""FastAPI dependency access to the shared RAG application."""

from __future__ import annotations

from typing import cast

from fastapi import Request

from src.application.use_cases import RagApplication


def get_application(request: Request) -> RagApplication:
    """Return the application instance installed by the factory."""
    return cast(RagApplication, request.app.state.rag_application)
