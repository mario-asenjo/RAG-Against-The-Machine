"""Acceptance tests for optional lexical plus semantic retrieval fusion."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Sequence

import fire
import pytest
import torch

from src.adapters.cli import RagCli
from src.application.use_cases import fuse_ranked_sources
from src.domain import MinimalSource, StudentSearchResults

ROOT = Path(__file__).resolve().parents[1]


class FakeEmbedder:
    """Provide the semantic model signature without loading model assets."""

    model_name = "fake/model"
    model_revision = "revision-1"
    max_length = 256

    def encode(self, texts: Sequence[str]) -> torch.Tensor:
        """Fail if a patched hybrid CLI test unexpectedly embeds text."""
        raise AssertionError(f"unexpected embedding call: {list(texts)}")


def source(path: str, start: int = 0, end: int = 10) -> MinimalSource:
    """Create one exact source identity for rank-fusion tests."""
    return MinimalSource(
        file_path=path,
        first_character_index=start,
        last_character_index=end,
    )


def test_rrf_combines_exact_duplicates_and_keeps_single_mode_sources() -> None:
    """A shared source gains both rank contributions and appears once."""
    lexical = [source("a.md"), source("shared.md")]
    semantic = [source("shared.md"), source("semantic.md")]

    fused = fuse_ranked_sources(lexical, semantic, k=3)

    assert [item.file_path for item in fused] == [
        "shared.md",
        "a.md",
        "semantic.md",
    ]
    assert fused.count(source("shared.md")) == 1


def test_rrf_counts_repeated_identity_once_per_retriever() -> None:
    """A malformed repeated row cannot gain extra same-mode contributions."""
    repeated = source("repeated.md")
    shared = source("shared.md")

    fused = fuse_ranked_sources(
        [repeated, repeated, shared],
        [shared],
        k=2,
    )

    assert fused == [shared, repeated]


def test_rrf_ties_are_canonical_and_near_duplicates_remain_distinct() -> None:
    """Ties use identity while overlapping spans stay separate."""
    later = source("same.md", 5, 15)
    earlier = source("same.md", 0, 10)

    fused = fuse_ranked_sources([later], [earlier], k=2)

    assert fused == [earlier, later]


@pytest.mark.parametrize("k", [-1, -10])
def test_rrf_rejects_negative_k(k: int) -> None:
    """Fusion rejects invalid limits at its reusable boundary."""
    with pytest.raises(ValueError, match="k must be non-negative"):
        fuse_ranked_sources([], [], k=k)


def test_rrf_zero_limit_returns_no_sources() -> None:
    """A zero limit deliberately returns no fused sources."""
    assert fuse_ranked_sources([source("a.md")], [source("b.md")], k=0) == []


def test_hybrid_single_search_calls_existing_retrievers_and_fuses(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The single-query adapter reuses both existing ranked search paths."""
    calls: list[tuple[str, str, int]] = []

    def lexical(index_path: Path, query: str, k: int) -> list[MinimalSource]:
        assert index_path == tmp_path / "lexical_index.sqlite3"
        calls.append(("lexical", query, k))
        return [source("a.md"), source("shared.md")]

    def semantic(
        semantic_path: Path,
        lexical_path: Path,
        query: str,
        k: int,
        embedder: FakeEmbedder,
    ) -> list[MinimalSource]:
        assert semantic_path == tmp_path / "semantic_index.pt"
        assert lexical_path == tmp_path / "lexical_index.sqlite3"
        calls.append(("semantic", query, k))
        return [source("shared.md"), source("semantic.md")]

    monkeypatch.setattr("src.adapters.cli.search_lexical_index", lexical)
    monkeypatch.setattr("src.adapters.cli.search_semantic_index", semantic)
    monkeypatch.setattr(
        "src.adapters.cli.MiniLmEmbedder",
        lambda **kwargs: FakeEmbedder(),
    )

    output = RagCli().search(
        "hybrid question",
        k=3,
        index_directory=str(tmp_path),
        hybrid=True,
    )

    assert calls == [
        ("lexical", "hybrid question", 3),
        ("semantic", "hybrid question", 3),
    ]
    assert output.splitlines() == [
        "shared.md [0:10]",
        "a.md [0:10]",
        "semantic.md [0:10]",
    ]


def test_hybrid_dataset_preserves_question_order_k_and_pydantic_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Batch hybrid search preserves the evaluator-facing wrapper contract."""
    questions = ["first", "second"]
    lexical_results = [
        [source("a.md"), source("shared.md")],
        [source("second.md")],
    ]
    semantic_results = [
        [source("shared.md"), source("semantic.md")],
        [source("other.md")],
    ]

    def lexical_batch(
        index_path: Path,
        queries: list[str],
        k: int,
        show_progress: bool,
    ) -> list[list[MinimalSource]]:
        assert index_path == tmp_path / "index" / "lexical_index.sqlite3"
        assert queries == questions
        assert k == 2
        assert show_progress is True
        return lexical_results

    def semantic_batch(
        semantic_path: Path,
        lexical_path: Path,
        queries: list[str],
        k: int,
        embedder: FakeEmbedder,
        show_progress: bool,
    ) -> list[list[MinimalSource]]:
        assert semantic_path == tmp_path / "index" / "semantic_index.pt"
        assert lexical_path == tmp_path / "index" / "lexical_index.sqlite3"
        assert queries == questions
        assert k == 2
        assert show_progress is True
        return semantic_results

    monkeypatch.setattr(
        "src.adapters.cli.search_lexical_index_batch",
        lexical_batch,
    )
    monkeypatch.setattr(
        "src.adapters.cli.search_semantic_index_batch",
        semantic_batch,
    )
    monkeypatch.setattr(
        "src.adapters.cli.MiniLmEmbedder",
        lambda **kwargs: FakeEmbedder(),
    )
    dataset_path = tmp_path / "questions.json"
    dataset_path.write_text(
        json.dumps(
            {
                "rag_questions": [
                    {"question_id": "q1", "question": questions[0]},
                    {"question_id": "q2", "question": questions[1]},
                ]
            }
        ),
        encoding="utf-8",
    )
    output_directory = tmp_path / "results"

    RagCli().search_dataset(
        dataset_path=str(dataset_path),
        k=2,
        save_directory=str(output_directory),
        index_directory=str(tmp_path / "index"),
        hybrid=True,
    )

    output = StudentSearchResults.model_validate_json(
        (output_directory / dataset_path.name).read_text(encoding="utf-8")
    )
    assert output.k == 2
    assert [item.question_id for item in output.search_results] == ["q1", "q2"]
    assert [item.question for item in output.search_results] == questions
    assert [
        [source.file_path for source in item.retrieved_sources]
        for item in output.search_results
    ] == [["shared.md", "a.md"], ["other.md", "second.md"]]


def test_hybrid_semantic_failure_preserves_existing_dataset_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stale failure remains clear and preserves prior JSON."""
    monkeypatch.setattr(
        "src.adapters.cli.search_lexical_index_batch",
        lambda *args, **kwargs: [[source("a.md")]],
    )

    def stale(*args: object, **kwargs: object) -> list[list[MinimalSource]]:
        raise ValueError(
            "semantic source_index_revision does not match the canonical index"
        )

    monkeypatch.setattr("src.adapters.cli.search_semantic_index_batch", stale)
    monkeypatch.setattr(
        "src.adapters.cli.MiniLmEmbedder",
        lambda **kwargs: FakeEmbedder(),
    )
    dataset_path = tmp_path / "questions.json"
    dataset_path.write_text(
        '{"rag_questions":[{"question_id":"q1","question":"query"}]}',
        encoding="utf-8",
    )
    output_directory = tmp_path / "results"
    output_directory.mkdir()
    output_path = output_directory / dataset_path.name
    output_path.write_text("previous", encoding="utf-8")

    with pytest.raises(
        fire.core.FireError,
        match="source_index_revision",
    ):
        RagCli().search_dataset(
            dataset_path=str(dataset_path),
            save_directory=str(output_directory),
            index_directory=str(tmp_path / "index"),
            hybrid=True,
        )

    assert output_path.read_text(encoding="utf-8") == "previous"


@pytest.mark.parametrize(
    "arguments",
    [
        ["search", "query"],
        ["search_dataset", "--dataset_path=missing.json"],
    ],
)
def test_cli_rejects_ambiguous_semantic_and_hybrid_without_traceback(
    arguments: list[str],
) -> None:
    """Mutually exclusive retrieval flags fail before touching index files."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src",
            *arguments,
            "--semantic=True",
            "--hybrid=True",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "mutually exclusive" in result.stderr
    assert "Traceback" not in result.stderr
