"""Adapter-neutral commands and results for shared RAG operations."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from src.domain import LexicalIndexMetadata

SemanticAction = Literal["built", "updated", "rebuilt", "unchanged"]


def validate_retrieval_mode(semantic: bool, hybrid: bool) -> None:
    """Reject ambiguous retrieval flags before adapter I/O."""
    if semantic and hybrid:
        raise ValueError("semantic and hybrid modes are mutually exclusive")


class IndexCommand(BaseModel):
    """Configuration shared by every index adapter."""

    max_chunk_size: int
    corpus_path: str
    save_directory: str
    incremental: bool
    semantic: bool
    semantic_model: str
    semantic_model_revision: str
    semantic_model_cache_directory: str
    semantic_max_length: int
    local_files_only: bool


class RetrievalCommand(BaseModel):
    """Configuration shared by single and dataset retrieval."""

    k: int
    index_directory: str
    semantic: bool = False
    hybrid: bool = False
    semantic_model: str = ""
    semantic_model_revision: str = ""
    semantic_model_cache_directory: str = ""
    semantic_max_length: int = 1
    local_files_only: bool = False
    cache: bool = False


class AnswerCommand(BaseModel):
    """Configuration shared by single-answer adapters."""

    k: int
    index_directory: str
    model_cache_directory: str
    token_budget: int
    max_new_tokens: int
    local_files_only: bool
    cache: bool


class IndexOperationResult(BaseModel):
    """Structured outcome of one full or incremental index operation."""

    operation: Literal["full", "fallback", "incremental", "unchanged"]
    metadata: LexicalIndexMetadata
    index_directory: str
    added_count: int = Field(default=0, ge=0)
    changed_count: int = Field(default=0, ge=0)
    deleted_count: int = Field(default=0, ge=0)
    semantic_action: SemanticAction | None = None
