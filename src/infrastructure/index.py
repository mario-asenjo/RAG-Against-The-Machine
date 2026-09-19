"""Atomic SQLite FTS5 persistence for the lexical BM25 index."""

from __future__ import annotations

import re
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Sequence

from tqdm import tqdm

from src.domain import (
    IndexedFile,
    LexicalIndexBuild,
    LexicalIndexMetadata,
    LexicalIndexUpdate,
    MinimalSource,
    SourceChunk,
)

INDEX_FILENAME = "lexical_index.sqlite3"

_SCHEMA = """
CREATE TABLE metadata (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    payload TEXT NOT NULL
);
CREATE TABLE files (
    file_path TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    byte_count INTEGER NOT NULL,
    character_count INTEGER NOT NULL
);
CREATE TABLE chunks (
    id INTEGER PRIMARY KEY,
    rank_order INTEGER NOT NULL UNIQUE,
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
                INSERT INTO files(
                    file_path,
                    content_hash,
                    byte_count,
                    character_count
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    (
                        item.file_path,
                        item.content_hash,
                        item.byte_count,
                        item.character_count,
                    )
                    for item in build.files
                ),
            )
            connection.executemany(
                """
                INSERT INTO chunks(
                    id,
                    rank_order,
                    file_path,
                    first_character_index,
                    last_character_index,
                    chunk_type,
                    text
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    (
                        chunk_id,
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
            connection.execute("PRAGMA user_version=2")
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
            ORDER BY rank_order
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


def load_index_files(index_path: Path) -> list[IndexedFile]:
    """Load the canonical persisted file manifest."""
    _require_index(index_path)
    with closing(sqlite3.connect(index_path)) as connection:
        _require_schema_v2(connection)
        rows = connection.execute(
            """
            SELECT file_path, content_hash, byte_count, character_count
            FROM files
            ORDER BY file_path
            """
        ).fetchall()
    return [
        IndexedFile(
            file_path=row[0],
            content_hash=row[1],
            byte_count=row[2],
            character_count=row[3],
        )
        for row in rows
    ]


def load_index_file_chunk_counts(index_path: Path) -> dict[str, int]:
    """Load persisted chunk counts keyed by exact file path."""
    _require_index(index_path)
    with closing(sqlite3.connect(index_path)) as connection:
        _require_schema_v2(connection)
        rows = connection.execute(
            """
            SELECT file_path, count(*)
            FROM chunks
            GROUP BY file_path
            """
        ).fetchall()
        files = connection.execute("SELECT file_path FROM files").fetchall()
    counts = {str(row[0]): int(row[1]) for row in rows}
    for row in files:
        counts.setdefault(str(row[0]), 0)
    return counts


def load_index_state(
    index_path: Path,
) -> tuple[
    LexicalIndexMetadata,
    list[IndexedFile],
    dict[str, int],
]:
    """Load one fully validated incremental-index lifecycle snapshot."""
    _require_index(index_path)
    with closing(sqlite3.connect(index_path)) as connection:
        return _validate_index_state(connection)


def update_lexical_index(
    update: LexicalIndexUpdate,
    index_path: Path,
) -> Path:
    """Apply a validated delta to a copy, then replace atomically."""
    _require_index(index_path)
    if not update.has_changes:
        return index_path
    temporary_path = index_path.with_name(f".{index_path.name}.tmp")
    temporary_path.unlink(missing_ok=True)
    try:
        shutil.copy2(index_path, temporary_path)
        with closing(sqlite3.connect(temporary_path)) as connection:
            _require_schema_v2(connection)
            connection.execute("BEGIN IMMEDIATE")
            affected_paths = [*update.changed_paths, *update.removed_paths]
            old_rows: list[tuple[int]] = []
            for path in affected_paths:
                old_rows.extend(
                    connection.execute(
                        "SELECT id FROM chunks WHERE file_path = ?",
                        (path,),
                    ).fetchall()
                )
            connection.executemany(
                "DELETE FROM chunks_fts WHERE rowid = ?",
                old_rows,
            )
            connection.executemany(
                "DELETE FROM chunks WHERE file_path = ?",
                ((path,) for path in affected_paths),
            )

            next_id = int(
                connection.execute(
                    "SELECT coalesce(max(id), 0) + 1 FROM chunks"
                ).fetchone()[0]
            )
            next_rank = int(
                connection.execute(
                    "SELECT coalesce(max(rank_order), 0) + 1 FROM chunks"
                ).fetchone()[0]
            )
            inserted = [
                (
                    next_id + offset,
                    next_rank + offset,
                    chunk.file_path,
                    chunk.first_character_index,
                    chunk.last_character_index,
                    chunk.chunk_type,
                    chunk.text,
                )
                for offset, chunk in enumerate(update.changed_chunks)
            ]
            connection.executemany(
                """
                INSERT INTO chunks(
                    id,
                    rank_order,
                    file_path,
                    first_character_index,
                    last_character_index,
                    chunk_type,
                    text
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                inserted,
            )
            connection.executemany(
                "INSERT INTO chunks_fts(rowid, text) VALUES (?, ?)",
                ((row[0], row[6]) for row in inserted),
            )
            connection.execute("DELETE FROM files")
            connection.executemany(
                """
                INSERT INTO files(
                    file_path,
                    content_hash,
                    byte_count,
                    character_count
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    (
                        item.file_path,
                        item.content_hash,
                        item.byte_count,
                        item.character_count,
                    )
                    for item in update.files
                ),
            )
            _renumber_ranks(connection)
            connection.execute(
                "UPDATE metadata SET payload = ? WHERE id = 1",
                (update.metadata.model_dump_json(),),
            )
            metadata, _, _ = _validate_index_state(connection)
            if metadata != update.metadata:
                raise ValueError("updated metadata does not match the plan")
            connection.commit()
        temporary_path.replace(index_path)
    except (OSError, sqlite3.Error, ValueError) as error:
        temporary_path.unlink(missing_ok=True)
        message = f"Could not update lexical index: {error}"
        raise RuntimeError(message) from error
    return index_path


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
            connection.execute("PRAGMA cache_size=-65536")
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
        ORDER BY bm25(chunks_fts), chunks.rank_order
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


def _require_schema_v2(connection: sqlite3.Connection) -> None:
    """Reject indexes that cannot be updated safely."""
    if connection.execute("PRAGMA user_version").fetchone() != (2,):
        raise ValueError("incremental index schema is incompatible")


def _renumber_ranks(connection: sqlite3.Connection) -> None:
    """Restore canonical full-build tie order without changing FTS row IDs."""
    connection.execute("UPDATE chunks SET rank_order = -id")
    rows = connection.execute(
        """
        SELECT id
        FROM chunks
        ORDER BY file_path, first_character_index, last_character_index, id
        """
    ).fetchall()
    connection.executemany(
        "UPDATE chunks SET rank_order = ? WHERE id = ?",
        ((rank, row[0]) for rank, row in enumerate(rows, start=1)),
    )


def _validate_index_state(
    connection: sqlite3.Connection,
) -> tuple[
    LexicalIndexMetadata,
    list[IndexedFile],
    dict[str, int],
]:
    """Validate and return one complete incremental lifecycle snapshot."""
    _require_schema_v2(connection)
    metadata_row = connection.execute(
        "SELECT payload FROM metadata WHERE id = 1"
    ).fetchone()
    if metadata_row is None:
        raise ValueError("index metadata is missing")
    metadata = LexicalIndexMetadata.model_validate_json(metadata_row[0])
    file_rows = connection.execute(
        """
        SELECT file_path, content_hash, byte_count, character_count
        FROM files
        ORDER BY file_path
        """
    ).fetchall()
    files = [
        IndexedFile(
            file_path=row[0],
            content_hash=row[1],
            byte_count=row[2],
            character_count=row[3],
        )
        for row in file_rows
    ]
    count_rows = connection.execute(
        "SELECT file_path, count(*) FROM chunks GROUP BY file_path"
    ).fetchall()
    counts = {str(row[0]): int(row[1]) for row in count_rows}
    for item in files:
        counts.setdefault(item.file_path, 0)
    chunk_count = sum(counts.values())
    orphan_count = int(
        connection.execute(
            """
            SELECT count(*)
            FROM chunks
            LEFT JOIN files USING (file_path)
            WHERE files.file_path IS NULL
            """
        ).fetchone()[0]
    )
    invalid_widths = int(
        connection.execute(
            """
            SELECT count(*)
            FROM chunks
            JOIN files USING (file_path)
            WHERE last_character_index <= first_character_index
               OR first_character_index < 0
               OR last_character_index > files.character_count
               OR last_character_index - first_character_index > ?
               OR length(text) != last_character_index - first_character_index
            """,
            (metadata.max_chunk_size,),
        ).fetchone()[0]
    )
    ranks = connection.execute(
        "SELECT rank_order, id FROM chunks ORDER BY rank_order"
    ).fetchall()
    canonical_ids = connection.execute(
        """
        SELECT id FROM chunks
        ORDER BY file_path, first_character_index, last_character_index, id
        """
    ).fetchall()
    connection.execute(
        """
        INSERT INTO chunks_fts(chunks_fts, rank)
        VALUES ('integrity-check', 1)
        """
    )
    integrity = connection.execute("PRAGMA integrity_check").fetchone()
    if len(files) != metadata.document_count:
        raise ValueError("file manifest count does not match metadata")
    if chunk_count != metadata.chunk_count:
        raise ValueError("chunk count does not match metadata")
    if orphan_count:
        raise ValueError("chunks exist outside the file manifest")
    if invalid_widths:
        raise ValueError("persisted chunk width is invalid")
    expected_ranks = list(range(1, chunk_count + 1))
    if [int(row[0]) for row in ranks] != expected_ranks:
        raise ValueError("persisted rank order is not contiguous")
    if [row[1] for row in ranks] != [row[0] for row in canonical_ids]:
        raise ValueError("persisted rank order is not canonical")
    if integrity != ("ok",):
        raise ValueError("SQLite integrity check failed")
    return metadata, files, counts
