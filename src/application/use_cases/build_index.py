"""Build the first lexical index input from exact corpus documents."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath

from tqdm import tqdm

from src.application.ports.chunking import Chunker
from src.domain import (
    LexicalIndexBuild,
    LexicalIndexMetadata,
    SourceChunk,
    SourceDocument,
)


def build_lexical_index(
    documents: Sequence[SourceDocument],
    chunkers: Mapping[str, Chunker],
    corpus_path: str,
    max_chunk_size: int = 2000,
    show_progress: bool = False,
) -> LexicalIndexBuild:
    """Chunk a corpus through injected strategies for lexical persistence."""
    if max_chunk_size <= 0:
        raise ValueError("max_chunk_size must be positive")

    chunks: list[SourceChunk] = []
    progress = tqdm(
        documents,
        desc="Chunking corpus",
        unit="file",
        disable=not show_progress,
    )
    for document in progress:
        suffix = PurePosixPath(document.file_path).suffix.lower()
        chunker = chunkers.get(suffix)
        if chunker is None:
            raise ValueError(f"No chunker configured for suffix: {suffix}")
        chunks.extend(chunker(document, max_chunk_size))

    metadata = LexicalIndexMetadata(
        corpus_path=corpus_path,
        max_chunk_size=max_chunk_size,
        document_count=len(documents),
        chunk_count=len(chunks),
    )
    return LexicalIndexBuild(metadata=metadata, chunks=chunks)
