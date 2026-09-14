"""Tests for ranked single and dataset lexical search."""

from __future__ import annotations

import json
import sqlite3
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
from src.infrastructure import (
    save_lexical_index,
    search_lexical_index,
    search_lexical_index_batch,
)


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


def test_batch_search_expands_sqlite_page_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Batch retrieval must retain its measured per-connection cache margin."""
    index_path = make_index(tmp_path)
    statements: list[str] = []
    real_connect = sqlite3.connect

    def traced_connect(path: str | Path) -> sqlite3.Connection:
        connection = real_connect(path)
        connection.set_trace_callback(statements.append)
        return connection

    monkeypatch.setattr(sqlite3, "connect", traced_connect)

    search_lexical_index_batch(index_path, ["vLLM"], k=1)

    assert "PRAGMA cache_size=-65536" in statements


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


def test_search_cli_emits_ranked_source_locations(tmp_path: Path) -> None:
    """Single search should print the subject's human-readable locations."""
    index_path = make_index(tmp_path)

    result = run_search(index_path.parent, "What is vLLM?", k=1)

    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        "data/raw/vllm-0.10.1/docs/serving.md [10:53]\n"
    )


@pytest.mark.parametrize(
    ("query", "k"),
    [("asdfghjkl zxcvbnm qwertyuiop", 10), ("vLLM", 0)],
)
def test_search_cli_returns_empty_output(
    tmp_path: Path,
    query: str,
    k: int,
) -> None:
    """No matches and zero limits succeed without diagnostics or sources."""
    index_path = make_index(tmp_path)

    result = run_search(index_path.parent, query, k)

    assert result.returncode == 0
    assert result.stdout == "\n"
    assert result.stderr == ""


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


def run_search_dataset(
    dataset_path: Path,
    index_directory: Path,
    save_directory: Path,
    k: int = 10,
) -> subprocess.CompletedProcess[str]:
    """Run dataset retrieval through the evaluator-facing CLI."""
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "src",
            "search_dataset",
            f"--dataset_path={dataset_path}",
            f"--k={k}",
            f"--save_directory={save_directory}",
            f"--index_directory={index_directory}",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_search_dataset_writes_subject_model_in_question_order(
    tmp_path: Path,
) -> None:
    """Batch search should preserve identity/order in StudentSearchResults."""
    index_path = make_index(tmp_path / "index")
    dataset_path = tmp_path / "dataset_docs_public.json"
    dataset_path.write_text(
        json.dumps(
            {
                "rag_questions": [
                    {"question_id": "q2", "question": "What is vLLM?"},
                    {"question_id": "q1", "question": "unknownterm"},
                ]
            }
        ),
        encoding="utf-8",
    )
    save_directory = tmp_path / "results"

    result = run_search_dataset(
        dataset_path,
        index_path.parent,
        save_directory,
        k=1,
    )

    output_path = save_directory / dataset_path.name
    assert result.returncode == 0, result.stderr
    assert output_path.as_posix() in result.stdout.replace("\\", "/")
    output = StudentSearchResults.model_validate_json(
        output_path.read_text(encoding="utf-8")
    )
    assert output.k == 1
    assert [item.question_id for item in output.search_results] == ["q2", "q1"]
    assert [item.question for item in output.search_results] == [
        "What is vLLM?",
        "unknownterm",
    ]
    assert len(output.search_results[0].retrieved_sources) == 1
    assert output.search_results[1].retrieved_sources == []


def test_search_dataset_k_zero_writes_empty_sources(tmp_path: Path) -> None:
    """A zero result limit should still preserve every dataset question."""
    index_path = make_index(tmp_path / "index")
    dataset_path = tmp_path / "questions.json"
    dataset_path.write_text(
        '{"rag_questions":[{"question_id":"q1","question":"vLLM"}]}',
        encoding="utf-8",
    )
    save_directory = tmp_path / "results"

    result = run_search_dataset(
        dataset_path,
        index_path.parent,
        save_directory,
        k=0,
    )

    assert result.returncode == 0, result.stderr
    output = StudentSearchResults.model_validate_json(
        (save_directory / dataset_path.name).read_text(encoding="utf-8")
    )
    assert output.k == 0
    assert output.search_results[0].retrieved_sources == []


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (None, "No such file or directory"),
        ("not json", "Invalid JSON"),
        ('{"rag_questions":[{"question_id":"q1"}]}', "question"),
    ],
)
def test_search_dataset_reports_invalid_input_without_traceback(
    tmp_path: Path,
    content: str | None,
    message: str,
) -> None:
    """Missing and malformed datasets should become clear Fire errors."""
    index_path = make_index(tmp_path / "index")
    dataset_path = tmp_path / "questions.json"
    if content is not None:
        dataset_path.write_text(content, encoding="utf-8")

    result = run_search_dataset(
        dataset_path,
        index_path.parent,
        tmp_path / "results",
    )

    assert result.returncode != 0
    assert message in result.stderr
    assert "Traceback" not in result.stderr


def test_search_dataset_rejects_negative_k_without_traceback(
    tmp_path: Path,
) -> None:
    """Negative batch limits should fail before writing invalid output."""
    index_path = make_index(tmp_path / "index")
    dataset_path = tmp_path / "questions.json"
    dataset_path.write_text('{"rag_questions":[]}', encoding="utf-8")

    result = run_search_dataset(
        dataset_path,
        index_path.parent,
        tmp_path / "results",
        k=-1,
    )

    assert result.returncode != 0
    assert "k must be non-negative" in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("kind", ["missing", "corrupt", "empty_query"])
def test_search_dataset_failure_preserves_existing_output(
    tmp_path: Path,
    kind: str,
) -> None:
    """Batch failures retain previous results and expose their cause."""
    index_directory = tmp_path / "index"
    query = "vLLM"
    if kind == "corrupt":
        index_directory.mkdir()
        (index_directory / "lexical_index.sqlite3").write_text(
            "not sqlite", encoding="utf-8"
        )
        message = "Could not search lexical index"
    elif kind == "empty_query":
        make_index(index_directory)
        query = ""
        message = "searchable terms"
    else:
        message = "Lexical index not found"
    dataset_path = tmp_path / "questions.json"
    dataset_path.write_text(
        json.dumps({"rag_questions": [{"question": query}]}),
        encoding="utf-8",
    )
    output_directory = tmp_path / "results"
    output_directory.mkdir()
    output_path = output_directory / dataset_path.name
    output_path.write_text("previous output", encoding="utf-8")

    result = run_search_dataset(
        dataset_path, index_directory, output_directory
    )

    assert result.returncode != 0
    assert result.stdout == ""
    assert message in result.stderr
    assert "Traceback" not in result.stderr
    assert output_path.read_text(encoding="utf-8") == "previous output"
