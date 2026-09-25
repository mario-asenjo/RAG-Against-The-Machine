"""Concrete local operations behind the shared RAG application."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from src.application.models import (
    AnswerCommand,
    IndexCommand,
    IndexOperationResult,
    RetrievalCommand,
    SemanticAction,
    validate_retrieval_mode,
)
from src.application.ports import Chunker, TextGenerator
from src.application.use_cases import (
    build_lexical_index,
    fuse_ranked_sources,
    plan_lexical_index_update,
)
from src.chunking import chunk_python_document, chunk_text_document
from src.domain import MinimalSource
from src.infrastructure import (
    INDEX_FILENAME,
    QwenGenerator,
    load_corpus,
    load_index_chunks,
    load_index_metadata,
    load_index_state,
    load_source_texts,
    save_lexical_index,
    search_lexical_index,
    search_lexical_index_batch,
    update_lexical_index,
)
from src.infrastructure.cache import (
    LEXICAL_RETRIEVER_SIGNATURE,
    cached_retrieval,
    hybrid_retriever_signature,
    semantic_retriever_signature,
)
from src.infrastructure.semantic import (
    SEMANTIC_INDEX_FILENAME,
    MiniLmEmbedder,
    build_semantic_index,
    ensure_semantic_index,
    load_semantic_index,
    search_semantic_index,
    search_semantic_index_batch,
    update_semantic_index,
)


class LocalPipelineOperations:
    """Implement shared pipeline operations with local files and CPU models."""

    def index(
        self,
        command: IndexCommand,
        show_progress: bool = False,
    ) -> IndexOperationResult:
        """Build canonical BM25 and optionally its semantic projection."""
        chunkers: dict[str, Chunker] = {
            ".md": chunk_text_document,
            ".py": chunk_python_document,
            ".txt": chunk_text_document,
        }
        corpus_root = Path(command.corpus_path)
        documents = load_corpus(corpus_root, show_progress=show_progress)
        index_path = Path(command.save_directory) / INDEX_FILENAME
        semantic_path = Path(command.save_directory) / SEMANTIC_INDEX_FILENAME
        semantic_action: SemanticAction | None
        fallback = False
        previous_revision = 0
        if command.incremental:
            try:
                previous_revision = load_index_metadata(
                    index_path
                ).index_revision
                current, existing_files, existing_counts = load_index_state(
                    index_path
                )
                if current.corpus_path != corpus_root.as_posix():
                    raise ValueError("indexed corpus path has changed")
                if current.max_chunk_size != command.max_chunk_size:
                    raise ValueError("indexed max_chunk_size has changed")
                existing_chunks = load_index_chunks(index_path)
                update = plan_lexical_index_update(
                    documents,
                    existing_files,
                    existing_counts,
                    existing_chunks,
                    chunkers,
                    corpus_root.as_posix(),
                    command.max_chunk_size,
                    current.index_revision,
                    show_progress=show_progress,
                )
            except (OSError, RuntimeError, ValueError, sqlite3.Error):
                fallback = True
            else:
                if not update.has_changes:
                    semantic_action = None
                    if command.semantic:
                        embedder = self._embedder(command, show_progress)
                        rebuilt = ensure_semantic_index(
                            existing_chunks,
                            semantic_path,
                            current.index_revision,
                            embedder,
                        )
                        semantic_action = (
                            "rebuilt" if rebuilt else "unchanged"
                        )
                    return IndexOperationResult(
                        operation="unchanged",
                        metadata=current,
                        index_directory=index_path.parent.as_posix(),
                        semantic_action=semantic_action,
                    )

                existing_paths = {item.file_path for item in existing_files}
                added = sum(
                    path not in existing_paths for path in update.changed_paths
                )
                changed = len(update.changed_paths) - added
                semantic_compatible = False
                if command.semantic:
                    embedder = self._embedder(command, show_progress)
                    try:
                        load_semantic_index(
                            semantic_path,
                            expected_source_index_revision=(
                                current.index_revision
                            ),
                            expected_model_name=embedder.model_name,
                            expected_model_revision=embedder.model_revision,
                            expected_max_length=embedder.max_length,
                            canonical_chunks=existing_chunks,
                        )
                    except (OSError, RuntimeError, ValueError):
                        pass
                    else:
                        semantic_compatible = True

                update_lexical_index(update, index_path)
                semantic_action = None
                if command.semantic:
                    canonical_chunks = load_index_chunks(index_path)
                    if semantic_compatible:
                        update_semantic_index(
                            semantic_path,
                            existing_chunks,
                            canonical_chunks,
                            update,
                            embedder,
                        )
                        semantic_action = "updated"
                    else:
                        build_semantic_index(
                            canonical_chunks,
                            semantic_path,
                            update.metadata.index_revision,
                            embedder,
                        )
                        semantic_action = "rebuilt"
                return IndexOperationResult(
                    operation="incremental",
                    metadata=update.metadata,
                    index_directory=index_path.parent.as_posix(),
                    added_count=added,
                    changed_count=changed,
                    deleted_count=len(update.removed_paths),
                    semantic_action=semantic_action,
                )

        index_revision = previous_revision + 1 if previous_revision else 1
        if not fallback:
            try:
                current, _, _ = load_index_state(index_path)
                index_revision = current.index_revision + 1
            except (OSError, RuntimeError, ValueError, sqlite3.Error):
                pass
        if command.semantic:
            try:
                semantic_metadata, _, _ = load_semantic_index(semantic_path)
                index_revision = max(
                    index_revision,
                    semantic_metadata.source_index_revision + 1,
                )
            except (OSError, RuntimeError, ValueError):
                pass
        build = build_lexical_index(
            documents,
            chunkers,
            corpus_root.as_posix(),
            command.max_chunk_size,
            show_progress=show_progress,
            index_revision=index_revision,
        )
        index_path = save_lexical_index(
            build,
            index_path,
            show_progress=show_progress,
        )
        semantic_action = None
        if command.semantic:
            embedder = self._embedder(command, show_progress)
            build_semantic_index(
                load_index_chunks(index_path),
                semantic_path,
                build.metadata.index_revision,
                embedder,
            )
            semantic_action = "built"
        else:
            semantic_path.unlink(missing_ok=True)
        return IndexOperationResult(
            operation="fallback" if fallback else "full",
            metadata=build.metadata,
            index_directory=index_path.parent.as_posix(),
            semantic_action=semantic_action,
        )

    def retrieve(
        self,
        command: RetrievalCommand,
        queries: list[str],
        batch: bool = False,
        show_progress: bool = False,
    ) -> list[list[MinimalSource]]:
        """Run lexical, semantic, or hybrid retrieval with optional caching."""
        validate_retrieval_mode(command.semantic, command.hybrid)
        lexical_path = Path(command.index_directory) / INDEX_FILENAME
        semantic_path = Path(command.index_directory) / SEMANTIC_INDEX_FILENAME
        signature = LEXICAL_RETRIEVER_SIGNATURE
        embedder: MiniLmEmbedder | None = None
        if command.semantic or command.hybrid:
            embedder = MiniLmEmbedder(
                cache_directory=Path(
                    command.semantic_model_cache_directory
                ),
                model_name=command.semantic_model,
                model_revision=command.semantic_model_revision,
                max_length=command.semantic_max_length,
                local_files_only=command.local_files_only,
                show_progress=show_progress,
            )
            semantic_signature = semantic_retriever_signature(
                command.semantic_model,
                command.semantic_model_revision,
                command.semantic_max_length,
            )
            signature = (
                hybrid_retriever_signature(semantic_signature)
                if command.hybrid
                else semantic_signature
            )

        def retrieve(items: list[str]) -> list[list[MinimalSource]]:
            semantic_embedder = cast(MiniLmEmbedder, embedder)
            if batch:
                return self._retrieve_batch(
                    command,
                    lexical_path,
                    semantic_path,
                    items,
                    semantic_embedder,
                    show_progress,
                )
            return [
                self._retrieve_one(
                    command,
                    lexical_path,
                    semantic_path,
                    query,
                    semantic_embedder,
                )
                for query in items
            ]

        return (
            cached_retrieval(
                lexical_path,
                queries,
                command.k,
                signature,
                retrieve,
            )
            if command.cache
            else retrieve(queries)
        )

    def load_source_texts(
        self,
        index_directory: str,
        sources: Sequence[MinimalSource],
    ) -> list[str]:
        """Hydrate exact sources from the canonical local index."""
        return load_source_texts(
            Path(index_directory) / INDEX_FILENAME,
            sources,
        )

    def make_generator(
        self,
        command: AnswerCommand,
        show_progress: bool = False,
    ) -> TextGenerator:
        """Construct the existing lazy local Qwen generator."""
        return QwenGenerator(
            cache_directory=Path(command.model_cache_directory),
            local_files_only=command.local_files_only,
            show_progress=show_progress,
        )

    @staticmethod
    def _embedder(
        command: IndexCommand,
        show_progress: bool,
    ) -> MiniLmEmbedder:
        """Construct the configured semantic index embedder."""
        return MiniLmEmbedder(
            cache_directory=Path(command.semantic_model_cache_directory),
            model_name=command.semantic_model,
            model_revision=command.semantic_model_revision,
            max_length=command.semantic_max_length,
            local_files_only=command.local_files_only,
            show_progress=show_progress,
        )

    @staticmethod
    def _retrieve_one(
        command: RetrievalCommand,
        lexical_path: Path,
        semantic_path: Path,
        query: str,
        embedder: MiniLmEmbedder,
    ) -> list[MinimalSource]:
        """Run one existing concrete retrieval path."""
        if command.hybrid:
            return fuse_ranked_sources(
                search_lexical_index(lexical_path, query, command.k),
                search_semantic_index(
                    semantic_path,
                    lexical_path,
                    query,
                    command.k,
                    embedder,
                ),
                command.k,
            )
        if command.semantic:
            return search_semantic_index(
                semantic_path,
                lexical_path,
                query,
                command.k,
                embedder,
            )
        return search_lexical_index(lexical_path, query, command.k)

    @staticmethod
    def _retrieve_batch(
        command: RetrievalCommand,
        lexical_path: Path,
        semantic_path: Path,
        queries: list[str],
        embedder: MiniLmEmbedder,
        show_progress: bool,
    ) -> list[list[MinimalSource]]:
        """Run one existing warm batch retrieval path."""
        if command.hybrid:
            lexical_sources = search_lexical_index_batch(
                lexical_path,
                queries,
                command.k,
                show_progress=show_progress,
            )
            semantic_sources = search_semantic_index_batch(
                semantic_path,
                lexical_path,
                queries,
                command.k,
                embedder,
                show_progress=show_progress,
            )
            return [
                fuse_ranked_sources(lexical, semantic, command.k)
                for lexical, semantic in zip(
                    lexical_sources,
                    semantic_sources,
                )
            ]
        if command.semantic:
            return search_semantic_index_batch(
                semantic_path,
                lexical_path,
                queries,
                command.k,
                embedder,
                show_progress=show_progress,
            )
        return search_lexical_index_batch(
            lexical_path,
            queries,
            command.k,
            show_progress=show_progress,
        )
