"""Build the first lexical index input from exact corpus documents."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath

from tqdm import tqdm

from src.application.ports.chunking import Chunker
from src.domain import (
    LexicalIndexBuild,
    LexicalIndexMetadata,
    IndexedFile,
    SourceChunk,
    SourceDocument,
)


def build_lexical_index(
    documents: Sequence[SourceDocument],
    chunkers: Mapping[str, Chunker],
    corpus_path: str,
    max_chunk_size: int = 2000,
    show_progress: bool = False,
    index_revision: int = 1,
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
        index_revision=index_revision,
    )
    return LexicalIndexBuild(
        metadata=metadata,
        chunks=chunks,
        files=[build_indexed_file(document) for document in documents],
    )


def build_indexed_file(document: SourceDocument) -> IndexedFile:
    """Hash one exact source document for lifecycle comparison."""
    encoded = document.text.encode("utf-8")
    return IndexedFile(
        file_path=document.file_path,
        content_hash=hashlib.sha256(encoded).hexdigest(),
        byte_count=len(encoded),
        character_count=len(document.text),
    )
