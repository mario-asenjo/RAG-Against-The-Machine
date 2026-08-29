"""Tests for evaluator-compatible dataset retrieval output."""

from __future__ import annotations

import json
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
from src.infrastructure import save_lexical_index

ROOT = Path(__file__).resolve().parents[1]


def make_index(tmp_path: Path) -> Path:
    """Persist a tiny real FTS5 index for dataset search tests."""
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
