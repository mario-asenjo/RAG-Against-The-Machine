"""Acceptance tests for sequential dataset answer generation."""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Sequence

import pytest
from fire.core import FireError

from src.adapters import cli as cli_module
from src.adapters.cli import RagCli
from src.application.use_cases.answer_question import ABSTENTION_ANSWER
from src.domain import (
    IndexedFile,
    LexicalIndexBuild,
    LexicalIndexMetadata,
    MinimalSearchResults,
    MinimalSource,
    SourceChunk,
    StudentSearchResults,
    StudentSearchResultsAndAnswer,
)
from src.infrastructure import save_lexical_index
from src.infrastructure import pipeline as pipeline_module

ROOT = Path(__file__).resolve().parents[1]


class BatchGenerator:
    """Record ordered batch generation without model assets."""

    def __init__(self, fail_on: str | None = None) -> None:
        self.fail_on = fail_on
        self.counted_questions: list[str] = []
        self.generated_questions: list[str] = []

    @property
    def supported_context_tokens(self) -> int:
        """Return enough context for fixture prompts."""
        return 40960

    def count_prompt_tokens(self, question: str, context: str) -> int:
        """Record calls and return a small complete-template count."""
        self.counted_questions.append(question)
        return 10 if not context else 20

    def generate(
        self,
        question: str,
        context: str,
        max_new_tokens: int,
    ) -> str:
        """Return the question as deterministic generated evidence."""
        del context, max_new_tokens
        self.generated_questions.append(question)
        if question == self.fail_on:
            raise RuntimeError("model failed during batch")
        return f"Answer for {question}"


def source(path: str, first: int, last: int) -> MinimalSource:
    """Build one exact source identity."""
    return MinimalSource(
        file_path=path,
        first_character_index=first,
        last_character_index=last,
    )


def make_index(tmp_path: Path) -> tuple[Path, list[SourceChunk]]:
    """Persist a tiny exact-source index."""
    chunks = [
        SourceChunk(
            file_path="data/raw/vllm-0.10.1/docs/a.md",
            first_character_index=0,
            last_character_index=5,
            chunk_type="text",
            text="alpha",
        ),
        SourceChunk(
            file_path="data/raw/vllm-0.10.1/vllm/b.py",
            first_character_index=10,
            last_character_index=14,
            chunk_type="python",
            text="beta",
        ),
    ]
    build = LexicalIndexBuild(
        metadata=LexicalIndexMetadata(
            corpus_path="data/raw/vllm-0.10.1",
            max_chunk_size=2000,
            document_count=2,
            chunk_count=2,
        ),
        chunks=chunks,
        files=[
            IndexedFile(
                file_path=chunk.file_path,
                content_hash="0" * 64,
                byte_count=len(chunk.text.encode("utf-8")),
                character_count=len(chunk.text),
            )
            for chunk in chunks
        ],
    )
    return save_lexical_index(
        build, tmp_path / "lexical_index.sqlite3"
    ), chunks


def write_search_results(
    path: Path,
    results: list[MinimalSearchResults],
    k: int = 2,
) -> None:
    """Write the exact Pydantic batch input contract."""
    output = StudentSearchResults(search_results=results, k=k)
    path.write_text(
        output.model_dump_json(indent=2),
        encoding="utf-8",
    )


def test_answer_dataset_preserves_contract_and_reuses_batch_resources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """One sequential loop must reuse one lazy generator and SQLite handle."""
    index_path, chunks = make_index(tmp_path / "index")
    first = MinimalSearchResults(
        question_id="q-2",
        question="second identity first",
        retrieved_sources=[
            source(chunks[1].file_path, 10, 14),
            source(chunks[0].file_path, 0, 5),
        ],
    )
    empty = MinimalSearchResults(
        question_id="q-empty",
        question="no evidence",
        retrieved_sources=[],
    )
    last = MinimalSearchResults(
        question_id="q-1",
        question="first identity last",
        retrieved_sources=[source(chunks[0].file_path, 0, 5)],
    )
    input_path = tmp_path / "public_search_results.json"
    write_search_results(input_path, [first, empty, last], k=7)
    output_directory = tmp_path / "answers"

    generator = BatchGenerator()
    generator_options: list[dict[str, object]] = []

    def make_generator(**options: object) -> BatchGenerator:
        generator_options.append(options)
        return generator

    monkeypatch.setattr(cli_module, "QwenGenerator", make_generator)
    monkeypatch.setattr(
        pipeline_module,
        "search_lexical_index",
        lambda *args, **kwargs: pytest.fail("answer_dataset reran retrieval"),
    )
    real_connect = sqlite3.connect
    connections: list[sqlite3.Connection] = []

    def counted_connect(database: str | Path) -> sqlite3.Connection:
        connection = real_connect(database)
        connections.append(connection)
        return connection

    monkeypatch.setattr(
        "src.adapters.cli.sqlite3.connect",
        counted_connect,
    )

    displayed = RagCli().answer_dataset(
        str(input_path),
        save_directory=str(output_directory),
        index_directory=str(index_path.parent),
        token_budget=100,
        max_new_tokens=10,
    )

    output_path = output_directory / input_path.name
    output = StudentSearchResultsAndAnswer.model_validate_json(
        output_path.read_text(encoding="utf-8")
    )
    assert output.k == 7
    assert [item.question_id for item in output.search_results] == [
        "q-2",
        "q-empty",
        "q-1",
    ]
    assert [item.question for item in output.search_results] == [
        first.question,
        empty.question,
        last.question,
    ]
    assert [item.retrieved_sources for item in output.search_results] == [
        first.retrieved_sources,
        [],
        last.retrieved_sources,
    ]
    assert [item.answer for item in output.search_results] == [
        f"Answer for {first.question}",
        ABSTENTION_ANSWER,
        f"Answer for {last.question}",
    ]
    assert generator.generated_questions == [first.question, last.question]
    assert generator_options == [
        {
            "cache_directory": Path("models/huggingface"),
            "local_files_only": False,
            "show_progress": True,
            "progress_position": 1,
            "progress_leave": False,
        }
    ]
    assert len(connections) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connections[0].execute("SELECT 1")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Answering dataset" in captured.err
    assert output_path.as_posix() in displayed.replace("\\", "/")


def test_answer_dataset_uses_stable_nested_progress_positions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dataset progress owns line 0; Qwen phases reuse line 1."""
    input_path = tmp_path / "empty.json"
    write_search_results(
        input_path,
        [MinimalSearchResults(question="No evidence", retrieved_sources=[])],
        k=0,
    )
    generator_options: list[dict[str, object]] = []
    tqdm_options: list[dict[str, object]] = []

    def make_generator(**options: object) -> BatchGenerator:
        generator_options.append(options)
        return BatchGenerator()

    def fake_tqdm(
        iterable: Sequence[object],
        **options: object,
    ) -> Sequence[object]:
        tqdm_options.append(options)
        return iterable

    monkeypatch.setattr(cli_module, "QwenGenerator", make_generator)
    monkeypatch.setattr(cli_module, "tqdm", fake_tqdm)

    RagCli().answer_dataset(
        str(input_path),
        save_directory=str(tmp_path / "answers"),
        index_directory=str(tmp_path / "missing-index"),
    )

    assert tqdm_options == [
        {
            "desc": "Answering dataset",
            "unit": "question",
            "position": 0,
            "leave": True,
        }
    ]
    assert generator_options == [
        {
            "cache_directory": Path("models/huggingface"),
            "local_files_only": False,
            "show_progress": True,
            "progress_position": 1,
            "progress_leave": False,
        }
    ]


def test_answer_dataset_empty_sources_abstain_without_index_or_model_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Evidence-free questions must not touch SQLite or lazy model methods."""
    input_path = tmp_path / "empty.json"
    search = MinimalSearchResults(
        question_id="q-empty",
        question="No evidence?",
        retrieved_sources=[],
    )
    write_search_results(input_path, [search], k=0)

    class UntouchableGenerator(BatchGenerator):
        """Fail if abstention initializes tokenizer or model behavior."""

        @property
        def supported_context_tokens(self) -> int:
            raise AssertionError("model assets were touched")

    monkeypatch.setattr(
        cli_module,
        "QwenGenerator",
        lambda **kwargs: UntouchableGenerator(),
    )
    monkeypatch.setattr(
        "src.adapters.cli.sqlite3.connect",
        lambda *args, **kwargs: pytest.fail("SQLite was opened"),
    )

    RagCli().answer_dataset(
        str(input_path),
        save_directory=str(tmp_path / "answers"),
        index_directory=str(tmp_path / "missing-index"),
    )

    output = StudentSearchResultsAndAnswer.model_validate_json(
        (tmp_path / "answers" / input_path.name).read_text(encoding="utf-8")
    )
    assert output.search_results[0].answer == ABSTENTION_ANSWER


def test_answer_dataset_failure_preserves_previous_output_atomically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A later failure must leave an earlier output byte-for-byte intact."""
    index_path, chunks = make_index(tmp_path / "index")
    input_path = tmp_path / "batch.json"
    write_search_results(
        input_path,
        [
            MinimalSearchResults(
                question_id="q1",
                question="works",
                retrieved_sources=[chunks[0]],
            ),
            MinimalSearchResults(
                question_id="q2",
                question="fails",
                retrieved_sources=[chunks[1]],
            ),
        ],
    )
    output_directory = tmp_path / "answers"
    output_directory.mkdir()
    output_path = output_directory / input_path.name
    output_path.write_bytes(b"previous output\r\n")
    monkeypatch.setattr(
        cli_module,
        "QwenGenerator",
        lambda **kwargs: BatchGenerator(fail_on="fails"),
    )

    with pytest.raises(FireError, match="model failed during batch"):
        RagCli().answer_dataset(
            str(input_path),
            save_directory=str(output_directory),
            index_directory=str(index_path.parent),
            token_budget=100,
            max_new_tokens=10,
        )

    assert output_path.read_bytes() == b"previous output\r\n"
    assert list(output_directory.glob(".*.tmp")) == []


def test_answer_dataset_replace_failure_preserves_previous_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Failure at atomic replacement must retain the prior destination."""
    input_path = tmp_path / "empty.json"
    write_search_results(input_path, [], k=0)
    output_directory = tmp_path / "answers"
    output_directory.mkdir()
    output_path = output_directory / input_path.name
    output_path.write_bytes(b"previous output\r\n")

    def fail_replace(source: Path, target: Path) -> Path:
        del source, target
        raise OSError("atomic replace blocked")

    monkeypatch.setattr(Path, "replace", fail_replace)

    with pytest.raises(FireError, match="atomic replace blocked"):
        RagCli().answer_dataset(
            str(input_path),
            save_directory=str(output_directory),
            index_directory=str(tmp_path / "missing-index"),
        )

    assert output_path.read_bytes() == b"previous output\r\n"
    assert list(output_directory.glob(".*.tmp")) == []


def test_answer_dataset_reports_stale_source_without_replacing_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An exact-source mismatch is a clear batch failure, not substitution."""
    index_path, _ = make_index(tmp_path / "index")
    input_path = tmp_path / "stale.json"
    write_search_results(
        input_path,
        [
            MinimalSearchResults(
                question="stale",
                retrieved_sources=[
                    source("data/raw/vllm-0.10.1/docs/a.md", 0, 4)
                ],
            )
        ],
    )
    output_directory = tmp_path / "answers"
    output_directory.mkdir()
    output_path = output_directory / input_path.name
    output_path.write_text("previous", encoding="utf-8")
    monkeypatch.setattr(
        cli_module,
        "QwenGenerator",
        lambda **kwargs: BatchGenerator(),
    )

    with pytest.raises(FireError, match="Exact source not found"):
        RagCli().answer_dataset(
            str(input_path),
            save_directory=str(output_directory),
            index_directory=str(index_path.parent),
            token_budget=100,
            max_new_tokens=10,
        )

    assert output_path.read_text(encoding="utf-8") == "previous"


def run_answer_dataset(
    input_path: Path,
    output_directory: Path,
    index_directory: Path,
    extra: Sequence[str] = (),
) -> subprocess.CompletedProcess[str]:
    """Run answer_dataset through the evaluator-facing Fire boundary."""
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "src",
            "answer_dataset",
            f"--student_search_results_path={input_path}",
            f"--save_directory={output_directory}",
            f"--index_directory={index_directory}",
            "--model_cache_directory=definitely-missing-model-cache",
            "--local_files_only=True",
            *extra,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_answer_dataset_cli_progress_is_stderr_only_and_json_is_clean(
    tmp_path: Path,
) -> None:
    """Batch progress must not contaminate stdout or serialized JSON."""
    input_path = tmp_path / "public.json"
    write_search_results(
        input_path,
        [
            MinimalSearchResults(
                question_id="q1",
                question="No retrieved evidence",
                retrieved_sources=[],
            )
        ],
        k=0,
    )
    output_directory = tmp_path / "answers"

    completed = run_answer_dataset(
        input_path,
        output_directory,
        tmp_path / "missing-index",
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.startswith(
        "Saved student_search_results_and_answer to "
    )
    assert "Answering dataset" not in completed.stdout
    assert "Answering dataset" in completed.stderr
    raw_output = (output_directory / input_path.name).read_text(
        encoding="utf-8"
    )
    assert "Answering dataset" not in raw_output
    output = StudentSearchResultsAndAnswer.model_validate_json(raw_output)
    assert output.search_results[0].answer == ABSTENTION_ANSWER


@pytest.mark.parametrize(
    ("kind", "message", "extra"),
    [
        ("missing_input", "No such file or directory", ()),
        ("malformed_json", "Invalid JSON", ()),
        ("missing_index", "Lexical index not found", ()),
        (
            "invalid_budget",
            "token_budget must be positive",
            ("--token_budget=0",),
        ),
        ("missing_model", "Could not load Qwen tokenizer", ()),
    ],
)
def test_answer_dataset_cli_failures_are_clear_and_traceback_free(
    tmp_path: Path,
    kind: str,
    message: str,
    extra: Sequence[str],
) -> None:
    """Input, index, budget, and model failures stay evaluator-safe."""
    index_directory = tmp_path / "index"
    input_path = tmp_path / "batch.json"
    if kind == "malformed_json":
        input_path.write_text("not json", encoding="utf-8")
    elif kind == "missing_input":
        pass
    elif kind == "invalid_budget":
        write_search_results(
            input_path,
            [MinimalSearchResults(question="empty", retrieved_sources=[])],
        )
    else:
        index_path, chunks = make_index(index_directory)
        del index_path
        write_search_results(
            input_path,
            [
                MinimalSearchResults(
                    question="alpha",
                    retrieved_sources=[chunks[0]],
                )
            ],
        )
        if kind == "missing_index":
            (index_directory / "lexical_index.sqlite3").unlink()
    output_directory = tmp_path / "answers"
    output_directory.mkdir()
    output_path = output_directory / input_path.name
    output_path.write_text("previous output", encoding="utf-8")

    completed = run_answer_dataset(
        input_path,
        output_directory,
        index_directory,
        extra,
    )

    assert completed.returncode != 0
    assert completed.stdout == ""
    assert message in completed.stderr
    assert "Traceback" not in completed.stderr
    assert output_path.read_text(encoding="utf-8") == "previous output"
