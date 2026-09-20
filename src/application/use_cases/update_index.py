"""Plan exact file-level updates for a persisted lexical index."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath

from tqdm import tqdm

from src.application.ports import Chunker
from src.application.use_cases.build_index import build_indexed_file
from src.domain import (
    IndexedFile,
    LexicalIndexMetadata,
    LexicalIndexUpdate,
    SourceChunk,
    SourceDocument,
)


def plan_lexical_index_update(
    documents: Sequence[SourceDocument],
    existing_files: Sequence[IndexedFile],
    existing_chunk_counts: Mapping[str, int],
    existing_chunks: Sequence[SourceChunk],
    chunkers: Mapping[str, Chunker],
    corpus_path: str,
    max_chunk_size: int,
    current_revision: int,
    show_progress: bool = False,
) -> LexicalIndexUpdate:
    """Hash all files and chunk only added or content-changed documents."""
    if max_chunk_size <= 0:
        raise ValueError("max_chunk_size must be positive")
    if current_revision <= 0:
        raise ValueError("current_revision must be positive")

    ordered_documents = sorted(documents, key=lambda item: item.file_path)
    files = [build_indexed_file(document) for document in ordered_documents]
    existing_by_path = {item.file_path: item for item in existing_files}
    current_by_path = {item.file_path: item for item in files}
    if len(existing_by_path) != len(existing_files):
        raise ValueError("persisted file manifest contains duplicate paths")
    if len(current_by_path) != len(files):
        raise ValueError("current corpus contains duplicate paths")

    changed_paths = [
        item.file_path
        for item in files
        if item.file_path not in existing_by_path
        or item != existing_by_path[item.file_path]
    ]
    removed_paths = sorted(set(existing_by_path) - set(current_by_path))
    changed_path_set = set(changed_paths)
    unchanged_paths = set(current_by_path) - changed_path_set
    documents_by_path = {
        document.file_path: document for document in ordered_documents
    }
    for chunk in existing_chunks:
        if chunk.file_path not in unchanged_paths:
            continue
        document = documents_by_path[chunk.file_path]
        expected = document.text[
            chunk.first_character_index:chunk.last_character_index
        ]
        if chunk.text != expected:
            raise ValueError(
                "persisted chunk does not match its exact source slice"
            )

    changed_chunks: list[SourceChunk] = []
    changed_documents = [
        document
        for document in ordered_documents
        if document.file_path in changed_path_set
    ]
    for document in tqdm(
        changed_documents,
        desc="Updating changed files",
        unit="file",
        disable=not show_progress,
    ):
        suffix = PurePosixPath(document.file_path).suffix.lower()
        chunker = chunkers.get(suffix)
        if chunker is None:
            raise ValueError(f"No chunker configured for suffix: {suffix}")
        document_chunks = chunker(document, max_chunk_size)
        for chunk in document_chunks:
            expected = document.text[
                chunk.first_character_index:chunk.last_character_index
            ]
            if chunk.file_path != document.file_path or chunk.text != expected:
                raise ValueError(
                    "incremental chunk does not match its exact source slice"
                )
        changed_chunks.extend(document_chunks)

    missing_counts = unchanged_paths - set(existing_chunk_counts)
    if missing_counts:
        raise ValueError(
            "persisted chunk counts are missing for: "
            f"{sorted(missing_counts)[0]}"
        )
    chunk_count = sum(
        existing_chunk_counts[path] for path in unchanged_paths
    ) + len(changed_chunks)
    has_changes = bool(changed_paths or removed_paths)
    metadata = LexicalIndexMetadata(
        corpus_path=corpus_path,
        max_chunk_size=max_chunk_size,
        document_count=len(files),
        chunk_count=chunk_count,
        index_revision=current_revision + int(has_changes),
    )
    return LexicalIndexUpdate(
        metadata=metadata,
        files=files,
        changed_paths=changed_paths,
        removed_paths=removed_paths,
        changed_chunks=changed_chunks,
        reused_file_count=len(unchanged_paths),
    )
