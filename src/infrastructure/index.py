"""Atomic SQLite FTS5 persistence for the lexical BM25 index."""

from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Sequence

from tqdm import tqdm

from src.domain import (
    LexicalIndexBuild,
    LexicalIndexMetadata,
    MinimalSource,
    SourceChunk,
)

INDEX_FILENAME = "lexical_index.sqlite3"

_SCHEMA = """
CREATE TABLE metadata (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    payload TEXT NOT NULL
);
CREATE TABLE chunks (
    id INTEGER PRIMARY KEY,
    file_path TEXT NOT NULL,
    first_character_index INTEGER NOT NULL,
    last_character_index INTEGER NOT NULL,
    chunk_type TEXT NOT NULL CHECK (chunk_type IN ('python', 'text')),
    text TEXT NOT NULL
);
CREATE VIRTUAL TABLE chunks_fts USING fts5(
    text,
    content='chunks',
    content_rowid='id',
    tokenize='unicode61'
);
"""


def save_lexical_index(
    build: LexicalIndexBuild,
    index_path: Path,
    show_progress: bool = False,
) -> Path:
    """Write a complete temporary index, then replace the target atomically."""
    index_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = index_path.with_name(f".{index_path.name}.tmp")
    temporary_path.unlink(missing_ok=True)

    try:
        with closing(sqlite3.connect(temporary_path)) as connection:
            connection.execute("PRAGMA journal_mode=OFF")
            connection.execute("PRAGMA synchronous=OFF")
            connection.executescript(_SCHEMA)
            connection.execute(
                "INSERT INTO metadata(id, payload) VALUES (1, ?)",
                (build.metadata.model_dump_json(),),
            )
            connection.executemany(
                """
                INSERT INTO chunks(
                    id,
                    file_path,
                    first_character_index,
                    last_character_index,
                    chunk_type,
                    text
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    (
                        chunk_id,
                        chunk.file_path,
                        chunk.first_character_index,
                        chunk.last_character_index,
                        chunk.chunk_type,
                        chunk.text,
                    )
                    for chunk_id, chunk in enumerate(build.chunks, start=1)
                ),
            )
            indexed_chunks = tqdm(
                enumerate(build.chunks, start=1),
                total=len(build.chunks),
                desc="Building BM25 index",
                unit="chunk",
                disable=not show_progress,
            )
            connection.executemany(
                "INSERT INTO chunks_fts(rowid, text) VALUES (?, ?)",
                (
                    (chunk_id, chunk.text)
                    for chunk_id, chunk in indexed_chunks
                ),
            )
            connection.execute("PRAGMA user_version=1")
            connection.commit()
        temporary_path.replace(index_path)
    except (OSError, sqlite3.Error) as error:
        temporary_path.unlink(missing_ok=True)
        message = f"Could not persist lexical index: {error}"
        raise RuntimeError(message) from error

    return index_path


def load_index_metadata(index_path: Path) -> LexicalIndexMetadata:
    """Reload and validate the persisted lexical index metadata."""
    _require_index(index_path)
    with closing(sqlite3.connect(index_path)) as connection:
        row = connection.execute(
            "SELECT payload FROM metadata WHERE id = 1"
        ).fetchone()
    if row is None:
        raise ValueError(f"Index metadata is missing: {index_path}")
    return LexicalIndexMetadata.model_validate_json(row[0])


def load_index_chunks(index_path: Path) -> list[SourceChunk]:
    """Reload exact source chunks in stable index order."""
    _require_index(index_path)
    with closing(sqlite3.connect(index_path)) as connection:
        rows = connection.execute(
            """
            SELECT
                file_path,
                first_character_index,
                last_character_index,
                chunk_type,
                text
            FROM chunks
            ORDER BY id
            """
        ).fetchall()
    return [
        SourceChunk(
            file_path=row[0],
            first_character_index=row[1],
            last_character_index=row[2],
            chunk_type=row[3],
            text=row[4],
        )
        for row in rows
    ]


def load_source_texts(
    index_path: Path,
    sources: Sequence[MinimalSource],
) -> list[str]:
    """Load each exact source tuple from SQLite in received order."""
    _require_index(index_path)
    try:
        with closing(sqlite3.connect(index_path)) as connection:
            return load_source_texts_from_connection(connection, sources)
    except sqlite3.Error as error:
        raise RuntimeError(
            f"Could not load exact source text: {error}"
        ) from error


def load_source_texts_from_connection(
    connection: sqlite3.Connection,
    sources: Sequence[MinimalSource],
) -> list[str]:
    """Load exact source tuples through a caller-owned SQLite connection."""
    try:
        texts: list[str] = []
        for source in sources:
            rows = connection.execute(
                """
                SELECT text
                FROM chunks
                WHERE file_path = ?
                  AND first_character_index = ?
                  AND last_character_index = ?
                """,
                (
                    source.file_path,
                    source.first_character_index,
                    source.last_character_index,
                ),
            ).fetchall()
            identity = (
                f"{source.file_path} "
                f"[{source.first_character_index}:"
                f"{source.last_character_index}]"
            )
            if not rows:
                raise ValueError(f"Exact source not found: {identity}")
            if len(rows) != 1:
                raise ValueError(f"Exact source is ambiguous: {identity}")
            texts.append(str(rows[0][0]))
        return texts
    except sqlite3.Error as error:
        raise RuntimeError(
            f"Could not load exact source text: {error}"
        ) from error


def search_lexical_index(
    index_path: Path,
    query: str,
    k: int = 10,
) -> list[MinimalSource]:
    """Return exact source spans ranked by SQLite FTS5 BM25."""
    if k < 0:
        raise ValueError("k must be non-negative")
    _require_index(index_path)
    try:
        with closing(sqlite3.connect(index_path)) as connection:
            return _search_connection(connection, query, k)
    except sqlite3.Error as error:
        message = f"Could not search lexical index: {error}"
        raise RuntimeError(message) from error


def search_lexical_index_batch(
    index_path: Path,
    queries: list[str],
    k: int = 10,
    show_progress: bool = False,
) -> list[list[MinimalSource]]:
    """Search ordered queries through one warm SQLite connection."""
    if k < 0:
        raise ValueError("k must be non-negative")
    _require_index(index_path)
    try:
        with closing(sqlite3.connect(index_path)) as connection:
            return [
                _search_connection(connection, query, k)
                for query in tqdm(
                    queries,
                    desc="Searching dataset",
                    unit="question",
                    disable=not show_progress,
                )
            ]
    except sqlite3.Error as error:
        message = f"Could not search lexical index: {error}"
        raise RuntimeError(message) from error


def _search_connection(
    connection: sqlite3.Connection,
    query: str,
    k: int,
) -> list[MinimalSource]:
    """Run one safe BM25 query through an existing connection."""
    tokens = re.findall(r"\w+", query)
    if not tokens:
        raise ValueError("query must contain searchable terms")
    match_query = " OR ".join(f'"{token}"' for token in tokens)
    rows = connection.execute(
        """
        SELECT
            chunks.file_path,
            chunks.first_character_index,
            chunks.last_character_index
        FROM chunks_fts
        JOIN chunks ON chunks.id = chunks_fts.rowid
        WHERE chunks_fts MATCH ?
        ORDER BY bm25(chunks_fts), chunks.id
        LIMIT ?
        """,
        (match_query, k),
    ).fetchall()
    return [
        MinimalSource(
            file_path=row[0],
            first_character_index=row[1],
            last_character_index=row[2],
        )
        for row in rows
    ]


def _require_index(index_path: Path) -> None:
    """Reject missing index paths without creating an empty SQLite file."""
    if not index_path.is_file():
        raise FileNotFoundError(f"Lexical index not found: {index_path}")
