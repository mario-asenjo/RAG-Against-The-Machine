"""Persistent SQLite cache for ordered exact retrieval results."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable, Sequence
from contextlib import closing
from pathlib import Path

from pydantic import TypeAdapter

from src.application.use_cases.fuse_retrieval import RRF_RANK_CONSTANT
from src.domain import LexicalIndexMetadata, MinimalSource
from src.infrastructure.index import load_index_metadata

CACHE_SCHEMA_VERSION = 1
LEXICAL_RETRIEVER_SIGNATURE = "lexical:sqlite-fts5-bm25:v1"

_SOURCE_LIST_ADAPTER = TypeAdapter(list[MinimalSource])
_CACHE_SCHEMA = """
CREATE TABLE IF NOT EXISTS query_cache (
    cache_schema_version INTEGER NOT NULL,
    index_revision INTEGER NOT NULL,
    retriever_signature TEXT NOT NULL,
    query_key TEXT NOT NULL,
    k INTEGER NOT NULL CHECK (k >= 0),
    results_json TEXT NOT NULL,
    PRIMARY KEY (
        cache_schema_version,
        index_revision,
        retriever_signature,
        query_key,
        k
    )
);
"""


def semantic_retriever_signature(
    model_name: str,
    model_revision: str,
    max_length: int,
) -> str:
    """Return a stable namespace for one semantic retrieval configuration."""
    return "semantic:" + json.dumps(
        {
            "algorithm": "minilm-mean-l2-cosine-v1",
            "max_length": max_length,
            "model": model_name,
            "revision": model_revision,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def hybrid_retriever_signature(semantic_signature: str) -> str:
    """Return a stable namespace for the fixed hybrid fusion configuration."""
    return "hybrid:" + json.dumps(
        {
            "fusion": "equal-rrf-v1",
            "lexical": LEXICAL_RETRIEVER_SIGNATURE,
            "rank_constant": RRF_RANK_CONSTANT,
            "semantic": semantic_signature,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def cached_retrieval(
    index_path: Path,
    queries: Sequence[str],
    k: int,
    retriever_signature: str,
    retrieve: Callable[[list[str]], list[list[MinimalSource]]],
) -> list[list[MinimalSource]]:
    """Return ordered persistent hits and retrieve each exact miss once."""
    if k < 0:
        raise ValueError("k must be non-negative")
    if not retriever_signature:
        raise ValueError("retriever_signature must not be empty")
    metadata = load_index_metadata(index_path)
    query_keys = [_query_key(query) for query in queries]
    resolved: dict[str, list[MinimalSource]] = {}
    missing: dict[str, str] = {}

    try:
        with closing(sqlite3.connect(index_path)) as connection:
            connection.executescript(_CACHE_SCHEMA)
            canonical_identities = _canonical_identities(connection)
            for query, query_key in zip(queries, query_keys):
                if query_key in resolved or query_key in missing:
                    continue
                row = connection.execute(
                    """
                    SELECT results_json
                    FROM query_cache
                    WHERE cache_schema_version = ?
                      AND index_revision = ?
                      AND retriever_signature = ?
                      AND query_key = ?
                      AND k = ?
                    """,
                    (
                        CACHE_SCHEMA_VERSION,
                        metadata.index_revision,
                        retriever_signature,
                        query_key,
                        k,
                    ),
                ).fetchone()
                cached = (
                    _validated_sources(
                        str(row[0]),
                        k,
                        canonical_identities,
                    )
                    if row is not None
                    else None
                )
                if cached is None:
                    if row is not None:
                        _delete_row(
                            connection,
                            metadata.index_revision,
                            retriever_signature,
                            query_key,
                            k,
                        )
                    missing[query_key] = query
                else:
                    resolved[query_key] = cached
            connection.commit()
    except sqlite3.Error as error:
        raise RuntimeError(
            f"Could not read retrieval cache: {error}"
        ) from error

    if missing:
        missing_keys = list(missing)
        fresh = retrieve([missing[key] for key in missing_keys])
        if len(fresh) != len(missing_keys):
            raise ValueError("retriever returned an unexpected result count")
        try:
            with closing(sqlite3.connect(index_path)) as connection:
                connection.executescript(_CACHE_SCHEMA)
                if _index_revision(connection) != metadata.index_revision:
                    raise ValueError("index revision changed during retrieval")
                canonical_identities = _canonical_identities(connection)
                for query_key, sources in zip(missing_keys, fresh):
                    if (
                        _validated_source_list(
                            sources,
                            k,
                            canonical_identities,
                        )
                        is None
                    ):
                        raise ValueError(
                            "retriever returned a non-canonical source"
                        )
                    payload = _SOURCE_LIST_ADAPTER.dump_json(sources).decode(
                        "utf-8"
                    )
                    connection.execute(
                        """
                        INSERT OR REPLACE INTO query_cache(
                            cache_schema_version,
                            index_revision,
                            retriever_signature,
                            query_key,
                            k,
                            results_json
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            CACHE_SCHEMA_VERSION,
                            metadata.index_revision,
                            retriever_signature,
                            query_key,
                            k,
                            payload,
                        ),
                    )
                    resolved[query_key] = sources
                connection.commit()
        except sqlite3.Error as error:
            raise RuntimeError(
                f"Could not persist retrieval cache: {error}"
            ) from error

    return [resolved[query_key] for query_key in query_keys]


def _query_key(query: str) -> str:
    """Hash the exact UTF-8 query without semantic normalization."""
    return hashlib.sha256(query.encode("utf-8")).hexdigest()


def _validated_sources(
    payload: str,
    k: int,
    canonical_identities: set[tuple[str, int, int]],
) -> list[MinimalSource] | None:
    """Validate untrusted cached JSON and every canonical chunk identity."""
    try:
        sources = _SOURCE_LIST_ADAPTER.validate_json(payload)
    except ValueError:
        return None
    return _validated_source_list(sources, k, canonical_identities)


def _validated_source_list(
    sources: list[MinimalSource],
    k: int,
    canonical_identities: set[tuple[str, int, int]],
) -> list[MinimalSource] | None:
    """Reject oversized, duplicate, or non-canonical source lists."""
    if len(sources) > k:
        return None
    identities = {
        (
            source.file_path,
            source.first_character_index,
            source.last_character_index,
        )
        for source in sources
    }
    if len(identities) != len(sources):
        return None
    if not identities <= canonical_identities:
        return None
    return sources


def _canonical_identities(
    connection: sqlite3.Connection,
) -> set[tuple[str, int, int]]:
    """Load the small canonical identity set once per cache operation."""
    return {
        (str(row[0]), int(row[1]), int(row[2]))
        for row in connection.execute(
            """
            SELECT file_path, first_character_index, last_character_index
            FROM chunks
            """
        )
    }


def _index_revision(connection: sqlite3.Connection) -> int:
    """Read the current revision through validated lexical metadata."""
    row = connection.execute(
        "SELECT payload FROM metadata WHERE id = 1"
    ).fetchone()
    if row is None:
        raise ValueError("index metadata is missing")
    return LexicalIndexMetadata.model_validate_json(row[0]).index_revision


def _delete_row(
    connection: sqlite3.Connection,
    index_revision: int,
    retriever_signature: str,
    query_key: str,
    k: int,
) -> None:
    """Delete one invalid row so a fresh result can replace it."""
    connection.execute(
        """
        DELETE FROM query_cache
        WHERE cache_schema_version = ?
          AND index_revision = ?
          AND retriever_signature = ?
          AND query_key = ?
          AND k = ?
        """,
        (
            CACHE_SCHEMA_VERSION,
            index_revision,
            retriever_signature,
            query_key,
            k,
        ),
    )
