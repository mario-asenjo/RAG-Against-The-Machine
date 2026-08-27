"""Application contract for interchangeable source chunking strategies."""

from __future__ import annotations

from typing import Protocol

from src.domain import SourceChunk, SourceDocument


class Chunker(Protocol):
    """Convert one loaded document into bounded exact source chunks."""

    def __call__(
        self,
        document: SourceDocument,
        max_chunk_size: int = 2000,
    ) -> list[SourceChunk]:
        """Chunk one document without changing its source coordinates."""
        ...
