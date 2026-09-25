"""FastAPI routers for the three approved local operations."""

from src.adapters.http.routers.answer import router as answer_router
from src.adapters.http.routers.index import router as index_router
from src.adapters.http.routers.search import router as search_router

__all__ = ["answer_router", "index_router", "search_router"]
