"""HTTP request and error models over shared application commands."""

from __future__ import annotations

from pydantic import BaseModel

from src.application.models import (
    AnswerCommand,
    IndexCommand,
    RetrievalCommand,
)
from src.infrastructure.semantic import (
    DEFAULT_SEMANTIC_MAX_LENGTH,
    DEFAULT_SEMANTIC_MODEL,
    DEFAULT_SEMANTIC_MODEL_REVISION,
)


class IndexRequest(IndexCommand):
    """Index request with the established CLI defaults."""

    max_chunk_size: int = 2000
    corpus_path: str = "data/raw/vllm-0.10.1"
    save_directory: str = "data/processed"
    incremental: bool = False
    semantic: bool = False
    semantic_model: str = DEFAULT_SEMANTIC_MODEL
    semantic_model_revision: str = DEFAULT_SEMANTIC_MODEL_REVISION
    semantic_model_cache_directory: str = "models/huggingface"
    semantic_max_length: int = DEFAULT_SEMANTIC_MAX_LENGTH
    local_files_only: bool = False


class SearchRequest(RetrievalCommand):
    """Single-query retrieval request with the established CLI defaults."""

    query: str
    k: int = 10
    index_directory: str = "data/processed"
    semantic: bool = False
    hybrid: bool = False
    semantic_model: str = DEFAULT_SEMANTIC_MODEL
    semantic_model_revision: str = DEFAULT_SEMANTIC_MODEL_REVISION
    semantic_model_cache_directory: str = "models/huggingface"
    semantic_max_length: int = DEFAULT_SEMANTIC_MAX_LENGTH
    local_files_only: bool = False
    cache: bool = False


class AnswerRequest(AnswerCommand):
    """Single-answer request with the established CLI defaults."""

    query: str
    k: int = 10
    index_directory: str = "data/processed"
    model_cache_directory: str = "models/huggingface"
    token_budget: int = 2048
    max_new_tokens: int = 128
    local_files_only: bool = False
    cache: bool = False


class ApiError(BaseModel):
    """Stable expected-error response."""

    error: str
