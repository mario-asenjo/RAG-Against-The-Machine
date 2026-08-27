"""Integration tests for the first persisted lexical index."""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

from src.infrastructure.index import (
    INDEX_FILENAME,
    load_index_chunks,
    load_index_metadata,
)

ROOT = Path(__file__).resolve().parents[1]


def run_index(corpus: Path, output: Path, max_chunk_size: int = 50) -> str:
    """Run the evaluator-facing index command against a tiny corpus."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src",
            "index",
            f"--corpus_path={corpus}",
            f"--save_directory={output}",
            f"--max_chunk_size={max_chunk_size}",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_index_cli_persists_reloadable_bm25_index_and_refreshes(
    tmp_path: Path,
) -> None:
    """Index metadata and exact chunks survive one deliberate full refresh."""
    corpus = tmp_path / "corpus"
    output = tmp_path / "processed"
    corpus.mkdir()
    readme = corpus / "README.md"
    module = corpus / "module.py"
    readme.write_text(
        "Alpha documentation.\n\n\n",
        encoding="utf-8",
        newline="",
    )
    module.write_text(
        "def answer() -> str:\n    return 'beta'\n",
        encoding="utf-8",
        newline="",
    )

    stdout = run_index(corpus, output)

    index_path = output / INDEX_FILENAME
    metadata = load_index_metadata(index_path)
    chunks = load_index_chunks(index_path)
    assert index_path.is_file()
    assert "Indexed 2 documents" in stdout
    assert metadata.retrieval_method == "sqlite-fts5-bm25"
    assert metadata.corpus_path == corpus.as_posix()
    assert metadata.document_count == 2
    assert metadata.chunk_count == len(chunks)
    assert metadata.max_chunk_size == 50
    assert {chunk.chunk_type for chunk in chunks} == {"python", "text"}
    for chunk in chunks:
        original = Path(chunk.file_path).read_text(
            encoding="utf-8",
        )
        assert chunk.text == original[
            chunk.first_character_index:chunk.last_character_index
        ]

    with closing(sqlite3.connect(index_path)) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        assert integrity == ("ok",)
        alpha_hits = connection.execute(
            "SELECT rowid FROM chunks_fts "
            "WHERE chunks_fts MATCH 'alpha' ORDER BY bm25(chunks_fts)"
        ).fetchall()
    assert alpha_hits

    readme.write_text(
        "Replacement documentation.\n\n\n",
        encoding="utf-8",
        newline="",
    )
    run_index(corpus, output)

    refreshed = load_index_metadata(index_path)
    refreshed_chunks = load_index_chunks(index_path)
    assert refreshed.document_count == 2
    assert refreshed.chunk_count == len(refreshed_chunks)
    assert "".join(
        chunk.text
        for chunk in refreshed_chunks
        if chunk.file_path == readme.as_posix()
    ) == readme.read_text(encoding="utf-8")
    with closing(sqlite3.connect(index_path)) as connection:
        old_hits = connection.execute(
            "SELECT count(*) FROM chunks_fts WHERE chunks_fts MATCH 'alpha'"
        ).fetchone()
        new_hits = connection.execute(
            "SELECT count(*) FROM chunks_fts "
            "WHERE chunks_fts MATCH 'replacement'"
        ).fetchone()
    assert old_hits == (0,)
    assert new_hits == (1,)


def test_index_cli_reports_missing_corpus_without_traceback(
    tmp_path: Path,
) -> None:
    """A missing corpus is an evaluator-safe CLI error, not a traceback."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src",
            "index",
            f"--corpus_path={tmp_path / 'missing'}",
            f"--save_directory={tmp_path / 'processed'}",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Corpus root not found" in result.stderr
    assert "Traceback" not in result.stderr
