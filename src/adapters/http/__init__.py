"""Local FastAPI adapter factory."""

from src.adapters.http.app import create_app

__all__ = ["create_app"]
