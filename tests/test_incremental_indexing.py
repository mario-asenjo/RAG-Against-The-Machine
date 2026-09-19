"""Acceptance tests for explicit incremental lexical indexing."""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pytest

from src.application.ports import Chunker
from src.application.use_cases import plan_lexical_index_update
from src.domain import IndexedFile, SourceChunk, SourceDocument
from src.infrastructure import (
    INDEX_FILENAME,
    load_index_chunks,
    load_index_file_chunk_counts,
    load_index_files,
    load_index_metadata,
    search_lexical_index,
    update_lexical_index,
)

ROOT = Path(__file__).resolve().parents[1]


def run_index(
    corpus: Path,
    output: Path,
    *,
    incremental: bool = False,
    max_chunk_size: int = 40,
) -> subprocess.CompletedProcess[str]:
    """Run the public index command against a fixture corpus."""
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "src",
            "index",
            f"--corpus_path={corpus}",
            f"--save_directory={output}",
            f"--max_chunk_size={max_chunk_size}",
            f"--incremental={incremental}",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def write_fixture_corpus(corpus: Path) -> tuple[Path, Path]:
    """Create two deterministic accepted source files."""
    python = corpus / "a.py"
    markdown = corpus / "b.md"
    corpus.mkdir()
    python.write_text("def alpha():\n    return 'alpha'\n", encoding="utf-8")
    markdown.write_text("Beta documentation.\n\n", encoding="utf-8")
    return python, markdown


def indexed_file(document: SourceDocument) -> IndexedFile:
    """Build the expected manifest identity for one exact document."""
    encoded = document.text.encode("utf-8")
    return IndexedFile(
        file_path=document.file_path,
        content_hash=hashlib.sha256(encoded).hexdigest(),
        byte_count=len(encoded),
        character_count=len(document.text),
    )


def test_full_rebuild_persists_versioned_file_manifest(tmp_path: Path) -> None:
    """A full build establishes schema v2 and revisioned file identities."""
    corpus = tmp_path / "corpus"
    write_fixture_corpus(corpus)
    output = tmp_path / "processed"

    result = run_index(corpus, output)

    assert result.returncode == 0, result.stderr
    index_path = output / INDEX_FILENAME
    metadata = load_index_metadata(index_path)
    files = load_index_files(index_path)
    counts = load_index_file_chunk_counts(index_path)
    assert metadata.schema_version == 2
    assert metadata.index_revision == 1
    assert metadata.document_count == len(files) == 2
    assert metadata.chunk_count == sum(counts.values())
    assert [item.file_path for item in files] == sorted(
        path.as_posix() for path in corpus.iterdir()
    )
    assert all(len(item.content_hash) == 64 for item in files)
    with closing(sqlite3.connect(index_path)) as connection:
        assert connection.execute("PRAGMA user_version").fetchone() == (2,)
        assert connection.execute("PRAGMA integrity_check").fetchone() == (
            "ok",
        )
        fts_count = connection.execute(
            "SELECT count(*) FROM chunks_fts"
        ).fetchone()
        assert fts_count == (metadata.chunk_count,)

    assert run_index(corpus, output).returncode == 0
    assert load_index_metadata(index_path).index_revision == 2


def test_full_rebuild_manifests_file_without_chunks(tmp_path: Path) -> None:
    """Whitespace-only accepted files remain visible to lifecycle detection."""
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    whitespace = corpus / "empty.txt"
    whitespace.write_text(" \n", encoding="utf-8")
    output = tmp_path / "processed"

    result = run_index(corpus, output)

    assert result.returncode == 0, result.stderr
    index_path = output / INDEX_FILENAME
    assert load_index_metadata(index_path).document_count == 1
    assert load_index_metadata(index_path).chunk_count == 0
    assert [item.file_path for item in load_index_files(index_path)] == [
        whitespace.as_posix()
    ]
    assert load_index_file_chunk_counts(index_path) == {
        whitespace.as_posix(): 0
    }


def test_incremental_noop_keeps_index_bytes_and_revision(
    tmp_path: Path,
) -> None:
    """An unchanged corpus must not rewrite or revise the live index."""
    corpus = tmp_path / "corpus"
    write_fixture_corpus(corpus)
    output = tmp_path / "processed"
    assert run_index(corpus, output).returncode == 0
    index_path = output / INDEX_FILENAME
    before = index_path.read_bytes()

    result = run_index(corpus, output, incremental=True)

    assert result.returncode == 0, result.stderr
    assert "unchanged" in result.stdout.lower()
    assert index_path.read_bytes() == before
    assert load_index_metadata(index_path).index_revision == 1


def test_incremental_plan_chunks_only_added_and_changed_documents() -> None:
    """Planning must reuse unchanged files without calling their chunker."""
    original = [
        SourceDocument(file_path="corpus/a.txt", text="same"),
        SourceDocument(file_path="corpus/b.txt", text="before"),
    ]
    current = [
        original[0],
        SourceDocument(file_path="corpus/b.txt", text="after!"),
        SourceDocument(file_path="corpus/c.txt", text="added"),
    ]
    called: list[str] = []

    def chunk(
        document: SourceDocument,
        max_chunk_size: int = 2000,
    ) -> list[SourceChunk]:
        called.append(document.file_path)
        return [
            SourceChunk(
                file_path=document.file_path,
                first_character_index=0,
                last_character_index=len(document.text),
                chunk_type="text",
                text=document.text,
            )
        ]

    plan = plan_lexical_index_update(
        current,
        [indexed_file(document) for document in original],
        {"corpus/a.txt": 1, "corpus/b.txt": 1},
        [
            SourceChunk(
                file_path=document.file_path,
                first_character_index=0,
                last_character_index=len(document.text),
                chunk_type="text",
                text=document.text,
            )
            for document in original
        ],
        {".txt": chunk},
        corpus_path="corpus",
        max_chunk_size=40,
        current_revision=1,
    )

    assert called == ["corpus/b.txt", "corpus/c.txt"]
    assert plan.changed_paths == ["corpus/b.txt", "corpus/c.txt"]
    assert plan.removed_paths == []
    assert plan.reused_file_count == 1
    assert plan.metadata.index_revision == 2


def test_incremental_plan_compares_complete_file_identity() -> None:
    """Matching hashes cannot hide corrupt persisted size diagnostics."""
    document = SourceDocument(file_path="corpus/a.txt", text="same")
    persisted = indexed_file(document).model_copy(
        update={"byte_count": 999, "character_count": 999}
    )

    def chunk(
        document: SourceDocument,
        max_chunk_size: int = 2000,
    ) -> list[SourceChunk]:
        return [
            SourceChunk(
                file_path=document.file_path,
                first_character_index=0,
                last_character_index=len(document.text),
                chunk_type="text",
                text=document.text,
            )
        ]

    plan = plan_lexical_index_update(
        [document],
        [persisted],
        {document.file_path: 1},
        [
            SourceChunk(
                file_path=document.file_path,
                first_character_index=0,
                last_character_index=len(document.text),
                chunk_type="text",
                text=document.text,
            )
        ],
        {".txt": chunk},
        corpus_path="corpus",
        max_chunk_size=40,
        current_revision=1,
    )

    assert plan.changed_paths == [document.file_path]
    assert plan.metadata.index_revision == 2


def test_incremental_plan_rejects_inexact_changed_chunk() -> None:
    """A changed chunk must remain an exact slice of its source document."""
    document = SourceDocument(file_path="corpus/a.txt", text="exact")

    def corrupt_chunk(
        document: SourceDocument,
        max_chunk_size: int = 2000,
    ) -> list[SourceChunk]:
        return [
            SourceChunk(
                file_path=document.file_path,
                first_character_index=0,
                last_character_index=5,
                chunk_type="text",
                text="wrong",
            )
        ]

    with pytest.raises(ValueError, match="exact source slice"):
        plan_lexical_index_update(
            [document],
            [],
            {},
            [],
            {".txt": corrupt_chunk},
            corpus_path="corpus",
            max_chunk_size=40,
            current_revision=1,
        )


def test_incremental_mixed_update_matches_clean_full_rebuild(
    tmp_path: Path,
) -> None:
    """Mixed changes remove stale terms and keep canonical ranking."""
    corpus = tmp_path / "corpus"
    python, markdown = write_fixture_corpus(corpus)
    output = tmp_path / "incremental"
    assert run_index(corpus, output).returncode == 0
    index_path = output / INDEX_FILENAME

    python.write_text(
        "def gamma():\n    return 'gamma gamma gamma gamma gamma'\n",
        encoding="utf-8",
    )
    markdown.unlink()
    renamed = corpus / "c.md"
    renamed.write_text("Delta documentation.\n\n", encoding="utf-8")

    result = run_index(corpus, output, incremental=True)

    assert result.returncode == 0, result.stderr
    assert "1 added" in result.stdout
    assert "1 changed" in result.stdout
    assert "1 deleted" in result.stdout
    metadata = load_index_metadata(index_path)
    assert metadata.index_revision == 2
    assert [item.file_path for item in load_index_files(index_path)] == [
        python.as_posix(),
        renamed.as_posix(),
    ]
    assert search_lexical_index(index_path, "alpha beta", 10) == []
    assert search_lexical_index(index_path, "gamma", 10)
    assert search_lexical_index(index_path, "delta", 10)

    full_output = tmp_path / "full"
    assert run_index(corpus, full_output).returncode == 0
    full_path = full_output / INDEX_FILENAME
    assert load_index_chunks(index_path) == load_index_chunks(full_path)
    for query in ("gamma", "delta", "documentation", "unknown"):
        incremental_results = search_lexical_index(index_path, query, 10)
        full_results = search_lexical_index(full_path, query, 10)
        assert incremental_results == full_results
    with closing(sqlite3.connect(index_path)) as connection:
        chunks = connection.execute("SELECT count(*) FROM chunks").fetchone()
        fts = connection.execute("SELECT count(*) FROM chunks_fts").fetchone()
        ranks = connection.execute(
            "SELECT rank_order FROM chunks ORDER BY rank_order"
        ).fetchall()
        assert connection.execute("PRAGMA integrity_check").fetchone() == (
            "ok",
        )
    assert chunks == fts == (metadata.chunk_count,)
    assert ranks == [(rank,) for rank in range(1, metadata.chunk_count + 1)]


def test_incremental_invalid_utf8_preserves_previous_index(
    tmp_path: Path,
) -> None:
    """A changed unreadable source must leave the live index untouched."""
    corpus = tmp_path / "corpus"
    python, _ = write_fixture_corpus(corpus)
    output = tmp_path / "processed"
    assert run_index(corpus, output).returncode == 0
    index_path = output / INDEX_FILENAME
    before = index_path.read_bytes()
    python.write_bytes(b"\xff")

    result = run_index(corpus, output, incremental=True)

    assert result.returncode != 0
    assert "Traceback" not in result.stderr
    assert index_path.read_bytes() == before


@pytest.mark.parametrize("failure", ["sqlite", "replace"])
def test_incremental_persistence_failure_preserves_previous_index(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    """SQLite and replacement failures must retain the previous database."""
    corpus = tmp_path / "corpus"
    python, _ = write_fixture_corpus(corpus)
    output = tmp_path / "processed"
    assert run_index(corpus, output).returncode == 0
    index_path = output / INDEX_FILENAME
    before = index_path.read_bytes()
    python.write_text(
        "def changed():\n    return 'changed'\n",
        encoding="utf-8",
    )

    documents = [
        SourceDocument(
            file_path=path.as_posix(),
            text=path.read_text(encoding="utf-8"),
        )
        for path in sorted(corpus.iterdir())
    ]
    calls: dict[str, Chunker] = {}

    def chunk(
        document: SourceDocument,
        max_chunk_size: int = 2000,
    ) -> list[SourceChunk]:
        return [
            SourceChunk(
                file_path=document.file_path,
                first_character_index=0,
                last_character_index=len(document.text),
                chunk_type="text",
                text=document.text,
            )
        ]

    calls[".py"] = chunk
    calls[".md"] = chunk
    plan = plan_lexical_index_update(
        documents,
        load_index_files(index_path),
        load_index_file_chunk_counts(index_path),
        load_index_chunks(index_path),
        calls,
        corpus_path=corpus.as_posix(),
        max_chunk_size=40,
        current_revision=1,
    )
    if failure == "sqlite":
        def corrupt_copy(source: Path, target: Path) -> Path:
            target.write_bytes(b"not sqlite")
            return target

        monkeypatch.setattr(shutil, "copy2", corrupt_copy)
    else:
        real_replace = Path.replace

        def fail_final_replace(source: Path, target: Path) -> Path:
            if source.name == f".{INDEX_FILENAME}.tmp":
                raise OSError("replacement failed")
            return real_replace(source, target)

        monkeypatch.setattr(Path, "replace", fail_final_replace)

    with pytest.raises(RuntimeError, match="Could not update lexical index"):
        update_lexical_index(plan, index_path)

    assert index_path.read_bytes() == before
    assert not index_path.with_name(f".{INDEX_FILENAME}.tmp").exists()


def test_incremental_incompatible_schema_falls_back_to_full_rebuild(
    tmp_path: Path,
) -> None:
    """Unknown lifecycle metadata must never be updated in place."""
    corpus = tmp_path / "corpus"
    write_fixture_corpus(corpus)
    output = tmp_path / "processed"
    assert run_index(corpus, output).returncode == 0
    index_path = output / INDEX_FILENAME
    with closing(sqlite3.connect(index_path)) as connection:
        connection.execute("PRAGMA user_version=1")
        connection.commit()

    result = run_index(corpus, output, incremental=True)

    assert result.returncode == 0, result.stderr
    assert "full rebuild fallback" in result.stdout.lower()
    assert load_index_metadata(index_path).index_revision == 2
    with closing(sqlite3.connect(index_path)) as connection:
        assert connection.execute("PRAGMA user_version").fetchone() == (2,)


@pytest.mark.parametrize(
    "corruption", ["metadata", "fts", "offsets", "text"]
)
def test_incremental_corruption_falls_back_to_full_rebuild(
    tmp_path: Path,
    corruption: str,
) -> None:
    """A no-op must validate lifecycle metadata and real FTS postings."""
    corpus = tmp_path / "corpus"
    write_fixture_corpus(corpus)
    output = tmp_path / "processed"
    assert run_index(corpus, output).returncode == 0
    index_path = output / INDEX_FILENAME

    with closing(sqlite3.connect(index_path)) as connection:
        if corruption == "metadata":
            metadata = load_index_metadata(index_path).model_copy(
                update={"chunk_count": 999}
            )
            connection.execute(
                "UPDATE metadata SET payload = ? WHERE id = 1",
                (metadata.model_dump_json(),),
            )
        elif corruption == "fts":
            row = connection.execute(
                "SELECT id FROM chunks WHERE text LIKE '%alpha%'"
            ).fetchone()
            assert row is not None
            connection.execute(
                "DELETE FROM chunks_fts WHERE rowid = ?",
                (row[0],),
            )
        elif corruption == "offsets":
            path = (corpus / "a.py").as_posix()
            connection.execute(
                """
                UPDATE chunks
                SET first_character_index = 100,
                    last_character_index = 133
                WHERE file_path = ?
                """,
                (path,),
            )
            connection.execute(
                """
                UPDATE files
                SET byte_count = 999, character_count = 1
                WHERE file_path = ?
                """,
                (path,),
            )
        else:
            row = connection.execute(
                "SELECT id, text FROM chunks WHERE text LIKE '%alpha%'"
            ).fetchone()
            assert row is not None
            corrupted_text = str(row[1]).replace("alpha", "omega")
            connection.execute(
                "DELETE FROM chunks_fts WHERE rowid = ?",
                (row[0],),
            )
            connection.execute(
                "UPDATE chunks SET text = ? WHERE id = ?",
                (corrupted_text, row[0]),
            )
            connection.execute(
                "INSERT INTO chunks_fts(rowid, text) VALUES (?, ?)",
                (row[0], corrupted_text),
            )
        connection.commit()

    result = run_index(corpus, output, incremental=True)

    assert result.returncode == 0, result.stderr
    assert "full rebuild fallback" in result.stdout.lower()
    metadata = load_index_metadata(index_path)
    assert metadata.chunk_count == len(load_index_chunks(index_path))
    assert search_lexical_index(index_path, "alpha", 10)
    assert search_lexical_index(index_path, "omega", 10) == []
