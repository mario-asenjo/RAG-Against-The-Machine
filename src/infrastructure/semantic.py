"""Local MiniLM embedding persistence and cosine retrieval."""

from __future__ import annotations

import pickle
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from tqdm import tqdm

from src.domain import (
    LexicalIndexUpdate,
    MinimalSource,
    SemanticIndexMetadata,
    SourceChunk,
)
from src.infrastructure.index import load_index_chunks, load_index_metadata

if TYPE_CHECKING:
    import torch

SEMANTIC_INDEX_FILENAME = "semantic_index.pt"
DEFAULT_SEMANTIC_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_SEMANTIC_MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
DEFAULT_SEMANTIC_MAX_LENGTH = 256


class Embedder(Protocol):
    """Small callable boundary needed by persistence and retrieval tests."""

    model_name: str
    model_revision: str
    max_length: int

    def encode(self, texts: Sequence[str]) -> torch.Tensor:
        """Return one normalized float32 row per text."""


class MiniLmEmbedder:
    """Lazily encode text with raw Transformers on CPU."""

    def __init__(
        self,
        cache_directory: Path,
        model_name: str = DEFAULT_SEMANTIC_MODEL,
        model_revision: str = DEFAULT_SEMANTIC_MODEL_REVISION,
        max_length: int = DEFAULT_SEMANTIC_MAX_LENGTH,
        local_files_only: bool = False,
        show_progress: bool = False,
        batch_size: int = 32,
    ) -> None:
        """Store model configuration without loading model assets."""
        if max_length <= 0:
            raise ValueError("semantic max_length must be positive")
        if batch_size <= 0:
            raise ValueError("semantic batch_size must be positive")
        self.model_name = model_name
        self.model_revision = model_revision
        self.max_length = max_length
        self._cache_directory = cache_directory
        self._local_files_only = local_files_only
        self._show_progress = show_progress
        self._batch_size = batch_size
        self._tokenizer: Any | None = None
        self._model: Any | None = None

    def encode(self, texts: Sequence[str]) -> torch.Tensor:
        """Mean-pool attention-masked hidden states and normalize each row."""
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer

            if self._model is None:
                options = {
                    "revision": self.model_revision,
                    "cache_dir": self._cache_directory,
                    "local_files_only": self._local_files_only,
                    "trust_remote_code": False,
                }
                tokenizer_factory: Any = AutoTokenizer
                model_factory: Any = AutoModel
                self._tokenizer = tokenizer_factory.from_pretrained(
                    self.model_name,
                    **options,
                )
                self._model = model_factory.from_pretrained(
                    self.model_name,
                    **options,
                    dtype=torch.float32,
                ).eval()
            assert self._tokenizer is not None
            assert self._model is not None
            if not texts:
                dimension = int(self._model.config.hidden_size)
                return torch.empty((0, dimension), dtype=torch.float32)

            batches: list[torch.Tensor] = []
            starts = range(0, len(texts), self._batch_size)
            for start in tqdm(
                starts,
                total=(len(texts) + self._batch_size - 1) // self._batch_size,
                desc="Embedding chunks",
                unit="batch",
                disable=not self._show_progress,
            ):
                inputs = self._tokenizer(
                    list(texts[start:start + self._batch_size]),
                    padding=True,
                    truncation=True,
                    max_length=self.max_length,
                    return_tensors="pt",
                )
                with torch.inference_mode():
                    hidden = self._model(**inputs).last_hidden_state
                mask = inputs["attention_mask"].unsqueeze(-1).to(hidden.dtype)
                pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(
                    min=1e-9
                )
                batches.append(
                    torch.nn.functional.normalize(pooled, p=2, dim=1).to(
                        dtype=torch.float32,
                        device="cpu",
                    )
                )
            return torch.cat(batches, dim=0)
        except (OSError, RuntimeError, ValueError) as error:
            raise RuntimeError(f"MiniLM embedding failed: {error}") from error


def build_semantic_index(
    chunks: Sequence[SourceChunk],
    index_path: Path,
    source_index_revision: int,
    embedder: Embedder,
) -> Path:
    """Build and atomically persist embeddings for canonical chunks."""
    embeddings = embedder.encode([chunk.text for chunk in chunks])
    metadata = SemanticIndexMetadata(
        model_name=embedder.model_name,
        model_revision=embedder.model_revision,
        max_length=embedder.max_length,
        embedding_dimension=_embedding_dimension(embeddings),
        chunk_count=len(chunks),
        source_index_revision=source_index_revision,
    )
    return _save_semantic_index(
        index_path,
        metadata,
        embeddings,
        [_source(chunk) for chunk in chunks],
    )


def ensure_semantic_index(
    chunks: Sequence[SourceChunk],
    index_path: Path,
    source_index_revision: int,
    embedder: Embedder,
) -> bool:
    """Keep a compatible projection or rebuild only that projection."""
    try:
        load_semantic_index(
            index_path,
            expected_source_index_revision=source_index_revision,
            expected_model_name=embedder.model_name,
            expected_model_revision=embedder.model_revision,
            expected_max_length=embedder.max_length,
            canonical_chunks=chunks,
        )
    except (OSError, RuntimeError, ValueError):
        build_semantic_index(
            chunks,
            index_path,
            source_index_revision,
            embedder,
        )
        return True
    return False


def update_semantic_index(
    index_path: Path,
    previous_chunks: Sequence[SourceChunk],
    canonical_chunks: Sequence[SourceChunk],
    update: LexicalIndexUpdate,
    embedder: Embedder,
) -> Path:
    """Reuse unchanged-file rows and embed every chunk of invalidated files."""
    import torch

    previous_revision = update.metadata.index_revision - 1
    metadata, embeddings, sources = load_semantic_index(
        index_path,
        expected_source_index_revision=previous_revision,
        expected_model_name=embedder.model_name,
        expected_model_revision=embedder.model_revision,
        expected_max_length=embedder.max_length,
        canonical_chunks=previous_chunks,
    )
    invalidated = set(update.changed_paths) | set(update.removed_paths)
    reused = {
        _identity(source): embeddings[position]
        for position, source in enumerate(sources)
        if source.file_path not in invalidated
    }
    changed_sources = [_source(chunk) for chunk in update.changed_chunks]
    if changed_sources:
        changed_embeddings = embedder.encode(
            [chunk.text for chunk in update.changed_chunks]
        )
        _validate_embeddings(changed_embeddings, len(changed_sources))
    else:
        changed_embeddings = torch.empty(
            (0, metadata.embedding_dimension),
            dtype=torch.float32,
        )
    replacements = {
        _identity(source): changed_embeddings[position]
        for position, source in enumerate(changed_sources)
    }

    final_sources = [_source(chunk) for chunk in canonical_chunks]
    rows: list[torch.Tensor] = []
    for source in final_sources:
        identity = _identity(source)
        row = replacements.get(identity)
        if row is None:
            row = reused.get(identity)
        if row is None:
            raise ValueError(
                "semantic update cannot resolve canonical chunk identity"
            )
        rows.append(row)
    final_embeddings = (
        torch.stack(rows).to(dtype=torch.float32, device="cpu")
        if rows
        else torch.empty(
            (0, metadata.embedding_dimension),
            dtype=torch.float32,
        )
    )
    final_metadata = SemanticIndexMetadata(
        model_name=embedder.model_name,
        model_revision=embedder.model_revision,
        max_length=embedder.max_length,
        embedding_dimension=metadata.embedding_dimension,
        chunk_count=len(final_sources),
        source_index_revision=update.metadata.index_revision,
    )
    return _save_semantic_index(
        index_path,
        final_metadata,
        final_embeddings,
        final_sources,
    )


def load_semantic_index(
    index_path: Path,
    *,
    expected_source_index_revision: int | None = None,
    expected_model_name: str | None = None,
    expected_model_revision: str | None = None,
    expected_max_length: int | None = None,
    canonical_chunks: Sequence[SourceChunk] | None = None,
) -> tuple[SemanticIndexMetadata, torch.Tensor, list[MinimalSource]]:
    """Load and validate one safe tensor artifact and optional expectations."""
    import torch

    if not index_path.is_file():
        raise FileNotFoundError(f"Semantic index not found: {index_path}")
    try:
        payload = torch.load(index_path, map_location="cpu", weights_only=True)
        if not isinstance(payload, dict):
            raise ValueError("semantic artifact payload must be a mapping")
        metadata = SemanticIndexMetadata.model_validate(payload["metadata"])
        embeddings = payload["embeddings"]
        raw_sources = payload["sources"]
        if not isinstance(raw_sources, list):
            raise ValueError("semantic artifact sources must be a list")
        sources = [MinimalSource.model_validate(item) for item in raw_sources]
    except (
        EOFError,
        KeyError,
        OSError,
        pickle.UnpicklingError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        raise ValueError(f"Invalid semantic index: {error}") from error

    _validate_embeddings(embeddings, metadata.chunk_count)
    if embeddings.shape[1] != metadata.embedding_dimension:
        raise ValueError(
            "semantic embedding dimension does not match metadata"
        )
    if len(sources) != metadata.chunk_count:
        raise ValueError("semantic source count does not match metadata")
    if (
        expected_source_index_revision is not None
        and metadata.source_index_revision != expected_source_index_revision
    ):
        raise ValueError(
            "semantic source_index_revision does not match the canonical index"
        )
    if (
        expected_model_name is not None
        and metadata.model_name != expected_model_name
    ):
        raise ValueError("semantic model name is incompatible")
    if (
        expected_model_revision is not None
        and metadata.model_revision != expected_model_revision
    ):
        raise ValueError("semantic model revision is incompatible")
    if (
        expected_max_length is not None
        and metadata.max_length != expected_max_length
    ):
        raise ValueError("semantic max_length is incompatible")
    if canonical_chunks is not None:
        canonical_sources = [_source(chunk) for chunk in canonical_chunks]
        if sources != canonical_sources:
            raise ValueError(
                "semantic chunk identities do not match the canonical store"
            )
    return metadata, embeddings, sources


def search_semantic_index(
    semantic_path: Path,
    lexical_path: Path,
    query: str,
    k: int,
    embedder: Embedder,
) -> list[MinimalSource]:
    """Rank canonical sources by normalized cosine dot product."""
    if k < 0:
        raise ValueError("k must be non-negative")
    if not query.strip():
        raise ValueError("query must contain searchable terms")
    embeddings, sources = _load_search_state(
        semantic_path,
        lexical_path,
        embedder,
    )
    if k == 0 or not sources:
        return []
    query_embedding = embedder.encode([query])
    _validate_query_embeddings(query_embedding, embeddings.shape[1], 1)
    scores = embeddings @ query_embedding[0]
    positions = _topk_positions(scores, min(k, len(sources)))
    return [sources[position] for position in positions]


def search_semantic_index_batch(
    semantic_path: Path,
    lexical_path: Path,
    queries: Sequence[str],
    k: int,
    embedder: Embedder,
    show_progress: bool = False,
) -> list[list[MinimalSource]]:
    """Embed ordered queries once and apply tensor cosine top-k."""
    if k < 0:
        raise ValueError("k must be non-negative")
    if any(not query.strip() for query in queries):
        raise ValueError("query must contain searchable terms")
    embeddings, sources = _load_search_state(
        semantic_path,
        lexical_path,
        embedder,
    )
    if k == 0 or not sources:
        return [[] for _ in queries]
    query_embeddings = embedder.encode(queries)
    _validate_query_embeddings(
        query_embeddings,
        embeddings.shape[1],
        len(queries),
    )
    scores = embeddings @ query_embeddings.T
    limit = min(k, len(sources))
    return [
        [sources[position] for position in _topk_positions(column, limit)]
        for column in tqdm(
            scores.T,
            desc="Searching semantic index",
            unit="question",
            disable=not show_progress,
        )
    ]


def _topk_positions(scores: torch.Tensor, k: int) -> list[int]:
    """Use tensor top-k and resolve boundary ties by canonical position."""
    import torch

    top_values = torch.topk(scores, k=k).values
    threshold = top_values[-1]
    candidates = torch.nonzero(scores >= threshold).flatten().tolist()
    return sorted(
        (int(position) for position in candidates),
        key=lambda position: (-float(scores[position]), position),
    )[:k]


def _load_search_state(
    semantic_path: Path,
    lexical_path: Path,
    embedder: Embedder,
) -> tuple[torch.Tensor, list[MinimalSource]]:
    """Require one projection over the current canonical SQLite revision."""
    metadata = load_index_metadata(lexical_path)
    chunks = load_index_chunks(lexical_path)
    _, embeddings, sources = load_semantic_index(
        semantic_path,
        expected_source_index_revision=metadata.index_revision,
        expected_model_name=embedder.model_name,
        expected_model_revision=embedder.model_revision,
        expected_max_length=embedder.max_length,
        canonical_chunks=chunks,
    )
    return embeddings, sources


def _save_semantic_index(
    index_path: Path,
    metadata: SemanticIndexMetadata,
    embeddings: torch.Tensor,
    sources: Sequence[MinimalSource],
) -> Path:
    """Validate, write beside the target, and atomically replace it."""
    import torch

    _validate_embeddings(embeddings, metadata.chunk_count)
    if embeddings.shape[1] != metadata.embedding_dimension:
        raise ValueError(
            "semantic embedding dimension does not match metadata"
        )
    if len(sources) != metadata.chunk_count:
        raise ValueError("semantic source count does not match metadata")
    index_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = index_path.with_name(f".{index_path.name}.tmp")
    temporary_path.unlink(missing_ok=True)
    try:
        torch.save(
            {
                "metadata": metadata.model_dump(mode="json"),
                "embeddings": embeddings.to(dtype=torch.float32, device="cpu"),
                "sources": [
                    source.model_dump(mode="json") for source in sources
                ],
            },
            temporary_path,
        )
        temporary_path.replace(index_path)
    except (OSError, RuntimeError) as error:
        temporary_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"Could not persist semantic index: {error}"
        ) from error
    return index_path


def _validate_embeddings(embeddings: Any, expected_rows: int) -> None:
    """Require finite, normalized float32 matrix rows."""
    import torch

    if not isinstance(embeddings, torch.Tensor):
        raise ValueError("semantic embeddings must be a tensor")
    if embeddings.dtype != torch.float32 or embeddings.ndim != 2:
        raise ValueError("semantic embeddings must be a float32 matrix")
    if embeddings.shape[0] != expected_rows or embeddings.shape[1] <= 0:
        raise ValueError("semantic embedding shape is invalid")
    if not torch.isfinite(embeddings).all():
        raise ValueError("semantic embeddings must be finite")
    if expected_rows:
        norms = torch.linalg.vector_norm(embeddings, dim=1)
        if not torch.allclose(norms, torch.ones_like(norms), atol=1e-5):
            raise ValueError("semantic embeddings must be L2-normalized")


def _validate_query_embeddings(
    embeddings: Any,
    expected_dimension: int,
    expected_rows: int,
) -> None:
    """Validate query output against the persisted vector space."""
    _validate_embeddings(embeddings, expected_rows)
    if embeddings.shape[1] != expected_dimension:
        raise ValueError("query embedding dimension is incompatible")


def _embedding_dimension(embeddings: Any) -> int:
    """Validate encoder output enough to construct artifact metadata."""
    if not hasattr(embeddings, "shape") or len(embeddings.shape) != 2:
        raise ValueError("semantic embeddings must be a matrix")
    dimension = int(embeddings.shape[1])
    _validate_embeddings(embeddings, int(embeddings.shape[0]))
    return dimension


def _source(chunk: SourceChunk) -> MinimalSource:
    """Drop text while preserving one exact canonical chunk identity."""
    return MinimalSource(
        file_path=chunk.file_path,
        first_character_index=chunk.first_character_index,
        last_character_index=chunk.last_character_index,
    )


def _identity(source: MinimalSource) -> tuple[str, int, int]:
    """Return the exact persisted chunk key."""
    return (
        source.file_path,
        source.first_character_index,
        source.last_character_index,
    )
