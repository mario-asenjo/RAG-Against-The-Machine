"""Tests for ranked lexical search and exact source projection."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from src.domain import (
    LexicalIndexBuild,
    LexicalIndexMetadata,
    SourceChunk,
    StudentSearchResults,
)
from src.infrastructure import save_lexical_index, search_lexical_index

ROOT = Path(__file__).resolve().parents[1]


def make_index(tmp_path: Path) -> Path:
    """Persist a tiny real FTS5 index for search tests."""
    chunks = [
        SourceChunk(
            file_path="data/raw/vllm-0.10.1/vllm/engine.py",
            first_character_index=100,
            last_character_index=126,
            chunk_type="python",
            text="vLLM compatibility layer.\n",
        ),
        SourceChunk(
            file_path="data/raw/vllm-0.10.1/docs/serving.md",
            first_character_index=10,
            last_character_index=53,
            chunk_type="text",
            text="vLLM vLLM is a fast model serving engine.\n\n",
        ),
    ]
    build = LexicalIndexBuild(
        metadata=LexicalIndexMetadata(
            corpus_path="data/raw/vllm-0.10.1",
            max_chunk_size=2000,
            document_count=2,
            chunk_count=len(chunks),
        ),
        chunks=chunks,
    )
    return save_lexical_index(build, tmp_path / "lexical_index.sqlite3")


def run_search(
    index_directory: Path,
    query: str = "vLLM",
    k: int = 10,
) -> subprocess.CompletedProcess[str]:
    """Run the evaluator-facing search command against a fixture index."""
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "src",
            "search",
            query,
            f"--k={k}",
            f"--index_directory={index_directory}",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_search_ranks_natural_language_and_projects_exact_source(
    tmp_path: Path,
) -> None:
    """Natural-language punctuation must not corrupt BM25 source output."""
    index_path = make_index(tmp_path)

    ranked = search_lexical_index(index_path, "What is vLLM?", k=2)
    limited = search_lexical_index(index_path, "What is vLLM?", k=1)

    assert [result.model_dump() for result in ranked] == [
        {
            "file_path": "data/raw/vllm-0.10.1/docs/serving.md",
            "first_character_index": 10,
            "last_character_index": 53,
        },
        {
            "file_path": "data/raw/vllm-0.10.1/vllm/engine.py",
            "first_character_index": 100,
            "last_character_index": 126,
        },
    ]
    assert limited == ranked[:1]


def test_search_rejects_query_without_searchable_terms(tmp_path: Path) -> None:
    """Empty or punctuation-only input must not reach FTS5 MATCH."""
    index_path = make_index(tmp_path)

    with pytest.raises(ValueError, match="searchable terms"):
        search_lexical_index(index_path, " ? - ", k=10)


def test_search_rejects_negative_k(tmp_path: Path) -> None:
    """Negative result limits are invalid at the reusable search boundary."""
    index_path = make_index(tmp_path)

    with pytest.raises(ValueError, match="k must be non-negative"):
        search_lexical_index(index_path, "vLLM", k=-1)


@pytest.mark.parametrize(
    ("query", "k"),
    [("asdfghjkl zxcvbnm qwertyuiop", 10), ("vLLM", 0)],
)
def test_search_deliberately_returns_no_sources(
    tmp_path: Path,
    query: str,
    k: int,
) -> None:
    """No matches and a zero limit both produce an intentional empty list."""
    assert search_lexical_index(make_index(tmp_path), query, k) == []


def test_search_cli_emits_subject_search_results_model(tmp_path: Path) -> None:
    """Single search should print the subject's search-results wrapper."""
    index_path = make_index(tmp_path)

    result = run_search(index_path.parent, "What is vLLM?", k=1)

    assert result.returncode == 0, result.stderr
    output = StudentSearchResults.model_validate_json(result.stdout)
    search_result = output.search_results[0]

    assert output.k == 1
    assert len(output.search_results) == 1
    assert search_result.question == "What is vLLM?"
    assert search_result.question_id
    retrieved_sources = [
        source.model_dump() for source in search_result.retrieved_sources
    ]
    assert retrieved_sources == [
        {
            "file_path": "data/raw/vllm-0.10.1/docs/serving.md",
            "first_character_index": 10,
            "last_character_index": 53,
        }
    ]


def test_search_cli_reports_corrupt_index_without_traceback(
    tmp_path: Path,
) -> None:
    """Invalid persisted data must become a clear CLI error."""
    (tmp_path / "lexical_index.sqlite3").write_text(
        "not a sqlite database",
        encoding="utf-8",
    )

    result = run_search(tmp_path)

    assert result.returncode != 0
    assert "Could not search lexical index" in result.stderr
    assert "Traceback" not in result.stderr


def test_search_cli_reports_missing_index_without_traceback(
    tmp_path: Path,
) -> None:
    """A missing generated index is a clear evaluator-safe error."""
    result = run_search(tmp_path)

    assert result.returncode != 0
    assert "Lexical index not found" in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize(
    ("query", "k", "message"),
    [("", 10, "searchable terms"), ("vLLM", -1, "k must be non-negative")],
)
def test_search_cli_rejects_invalid_input_without_traceback(
    tmp_path: Path,
    query: str,
    k: int,
    message: str,
) -> None:
    """Evaluator edge inputs receive deliberate Fire errors."""
    index_path = make_index(tmp_path)

    result = run_search(index_path.parent, query, k)

    assert result.returncode != 0
    assert message in result.stderr
    assert "Traceback" not in result.stderr
