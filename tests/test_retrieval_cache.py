"""Acceptance tests for the persistent retrieval-result cache."""

from __future__ import annotations

import inspect
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pytest

from src.adapters import cli as cli_module
from src.adapters.cli import RagCli
from src.domain import (
    IndexedFile,
    LexicalIndexBuild,
    LexicalIndexMetadata,
    MinimalSource,
    SourceChunk,
)
from src.infrastructure import save_lexical_index
from src.infrastructure.cache import (
    LEXICAL_RETRIEVER_SIGNATURE,
    cached_retrieval,
    hybrid_retriever_signature,
    semantic_retriever_signature,
)

ROOT = Path(__file__).resolve().parents[1]


def source(path: str, start: int, end: int) -> MinimalSource:
    """Create one exact cacheable source identity."""
    return MinimalSource(
        file_path=path,
        first_character_index=start,
        last_character_index=end,
    )


def make_index(
    tmp_path: Path,
    revision: int = 1,
) -> tuple[Path, MinimalSource]:
    """Persist one canonical chunk for cache validation tests."""
    chunk = SourceChunk(
        file_path="data/raw/vllm-0.10.1/docs/cache.md",
        first_character_index=0,
        last_character_index=10,
        chunk_type="text",
        text="cache text",
    )
    build = LexicalIndexBuild(
        metadata=LexicalIndexMetadata(
            corpus_path="data/raw/vllm-0.10.1",
            max_chunk_size=2000,
            document_count=1,
            chunk_count=1,
            index_revision=revision,
        ),
        chunks=[chunk],
        files=[
            IndexedFile(
                file_path=chunk.file_path,
                content_hash="0" * 64,
                byte_count=len(chunk.text),
                character_count=len(chunk.text),
            )
        ],
    )
    path = save_lexical_index(build, tmp_path / "lexical_index.sqlite3")
    return path, source(chunk.file_path, 0, 10)


def cache_row_count(index_path: Path) -> int:
    """Return persisted rows after a cache-enabled operation."""
    with closing(sqlite3.connect(index_path)) as connection:
        return int(
            connection.execute(
                "SELECT count(*) FROM query_cache"
            ).fetchone()[0]
        )


def test_second_independent_call_is_persistent_hit(tmp_path: Path) -> None:
    """A later adapter instance reuses ordered exact sources from SQLite."""
    index_path, expected = make_index(tmp_path)
    calls: list[list[str]] = []

    def retrieve(queries: list[str]) -> list[list[MinimalSource]]:
        calls.append(queries)
        return [[expected] for _ in queries]

    first = cached_retrieval(
        index_path,
        ["same query"],
        1,
        LEXICAL_RETRIEVER_SIGNATURE,
        retrieve,
    )
    second = cached_retrieval(
        index_path,
        ["same query"],
        1,
        LEXICAL_RETRIEVER_SIGNATURE,
        lambda queries: pytest.fail(f"unexpected miss: {queries}"),
    )

    assert first == second == [[expected]]
    assert calls == [["same query"]]
    assert cache_row_count(index_path) == 1


def test_repeated_batch_query_executes_one_miss(tmp_path: Path) -> None:
    """Duplicate queries in one batch share one persisted retrieval result."""
    index_path, expected = make_index(tmp_path)
    calls: list[list[str]] = []

    def retrieve(queries: list[str]) -> list[list[MinimalSource]]:
        calls.append(queries)
        return [[expected] for _ in queries]

    results = cached_retrieval(
        index_path,
        ["repeat", "repeat", "other"],
        1,
        LEXICAL_RETRIEVER_SIGNATURE,
        retrieve,
    )

    assert results == [[expected], [expected], [expected]]
    assert calls == [["repeat", "other"]]
    assert cache_row_count(index_path) == 2


def test_query_k_signature_and_revision_changes_are_misses(
    tmp_path: Path,
) -> None:
    """Every logical key dimension independently invalidates reuse."""
    index_path, expected = make_index(tmp_path)
    calls: list[list[str]] = []

    def retrieve(queries: list[str]) -> list[list[MinimalSource]]:
        calls.append(queries)
        return [[expected] for _ in queries]

    cached_retrieval(
        index_path,
        ["query"],
        1,
        LEXICAL_RETRIEVER_SIGNATURE,
        retrieve,
    )
    cached_retrieval(
        index_path,
        ["different"],
        1,
        LEXICAL_RETRIEVER_SIGNATURE,
        retrieve,
    )
    cached_retrieval(
        index_path,
        ["query"],
        2,
        LEXICAL_RETRIEVER_SIGNATURE,
        retrieve,
    )
    cached_retrieval(
        index_path,
        ["query"],
        1,
        "lexical:changed",
        retrieve,
    )
    with closing(sqlite3.connect(index_path)) as connection:
        metadata = LexicalIndexMetadata.model_validate_json(
            connection.execute(
                "SELECT payload FROM metadata WHERE id = 1"
            ).fetchone()[0]
        ).model_copy(update={"index_revision": 2})
        connection.execute(
            "UPDATE metadata SET payload = ? WHERE id = 1",
            (metadata.model_dump_json(),),
        )
        connection.commit()
    cached_retrieval(
        index_path,
        ["query"],
        1,
        LEXICAL_RETRIEVER_SIGNATURE,
        retrieve,
    )

    assert calls == [
        ["query"],
        ["different"],
        ["query"],
        ["query"],
        ["query"],
    ]
    assert cache_row_count(index_path) == 5


def test_full_rebuild_drops_cache_on_revision_reset(tmp_path: Path) -> None:
    """Atomic SQLite replacement cannot reuse rows from the previous corpus."""
    index_path, expected = make_index(tmp_path, revision=1)
    cached_retrieval(
        index_path,
        ["query"],
        1,
        LEXICAL_RETRIEVER_SIGNATURE,
        lambda queries: [[expected] for _ in queries],
    )

    rebuilt_path, rebuilt_source = make_index(tmp_path, revision=1)
    calls = 0

    def retrieve(queries: list[str]) -> list[list[MinimalSource]]:
        nonlocal calls
        calls += 1
        return [[rebuilt_source] for _ in queries]

    cached_retrieval(
        rebuilt_path,
        ["query"],
        1,
        LEXICAL_RETRIEVER_SIGNATURE,
        retrieve,
    )

    assert calls == 1
    assert cache_row_count(rebuilt_path) == 1


def test_malformed_or_noncanonical_rows_are_replaced(tmp_path: Path) -> None:
    """Validate persisted JSON and identities before trusting them."""
    index_path, expected = make_index(tmp_path)
    cached_retrieval(
        index_path,
        ["query"],
        1,
        LEXICAL_RETRIEVER_SIGNATURE,
        lambda queries: [[expected]],
    )
    with closing(sqlite3.connect(index_path)) as connection:
        connection.execute(
            "UPDATE query_cache SET results_json = ?",
            ('[{"file_path":"missing","first_character_index":0,'
             '"last_character_index":1}]',),
        )
        connection.commit()
    calls = 0

    def retrieve(queries: list[str]) -> list[list[MinimalSource]]:
        nonlocal calls
        calls += 1
        return [[expected]]

    result = cached_retrieval(
        index_path,
        ["query"],
        1,
        LEXICAL_RETRIEVER_SIGNATURE,
        retrieve,
    )

    assert result == [[expected]]
    assert calls == 1
    assert cache_row_count(index_path) == 1


def test_retrieval_errors_are_not_cached(tmp_path: Path) -> None:
    """A failed miss creates no successful cache row."""
    index_path, _ = make_index(tmp_path)

    def fail(queries: list[str]) -> list[list[MinimalSource]]:
        raise RuntimeError("retrieval failed")

    with pytest.raises(RuntimeError, match="retrieval failed"):
        cached_retrieval(
            index_path,
            ["query"],
            1,
            LEXICAL_RETRIEVER_SIGNATURE,
            fail,
        )

    assert cache_row_count(index_path) == 0


def test_cache_write_errors_leave_no_successful_row(tmp_path: Path) -> None:
    """A failed SQLite insert never looks like a persistent hit."""
    index_path, expected = make_index(tmp_path)

    def fail_insert(queries: list[str]) -> list[list[MinimalSource]]:
        with closing(sqlite3.connect(index_path)) as connection:
            connection.execute(
                """
                CREATE TRIGGER reject_cache_insert
                BEFORE INSERT ON query_cache
                BEGIN
                    SELECT RAISE(ABORT, 'cache write failed');
                END
                """
            )
            connection.commit()
        return [[expected] for _ in queries]

    with pytest.raises(
        RuntimeError,
        match="Could not persist retrieval cache",
    ):
        cached_retrieval(
            index_path,
            ["query"],
            1,
            LEXICAL_RETRIEVER_SIGNATURE,
            fail_insert,
        )

    assert cache_row_count(index_path) == 0


def test_retriever_signatures_cover_configuration() -> None:
    """Model and fusion changes create distinct cache namespaces."""
    first = semantic_retriever_signature("model", "revision-a", 256)
    second = semantic_retriever_signature("model", "revision-b", 256)

    assert first != second
    assert hybrid_retriever_signature(first) != hybrid_retriever_signature(
        second
    )
    assert LEXICAL_RETRIEVER_SIGNATURE not in {first, second}


@pytest.mark.parametrize(
    ("semantic", "hybrid", "revision", "expected_signature"),
    [
        (False, False, "unused", LEXICAL_RETRIEVER_SIGNATURE),
        (
            True,
            False,
            "1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
            semantic_retriever_signature(
                "sentence-transformers/all-MiniLM-L6-v2",
                "1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
                256,
            ),
        ),
        (
            False,
            True,
            "1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
            hybrid_retriever_signature(
                semantic_retriever_signature(
                    "sentence-transformers/all-MiniLM-L6-v2",
                    "1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
                    256,
                )
            ),
        ),
        (
            True,
            False,
            "changed",
            semantic_retriever_signature(
                "sentence-transformers/all-MiniLM-L6-v2",
                "changed",
                256,
            ),
        ),
    ],
)
def test_search_uses_mode_and_model_specific_cache_signature(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    semantic: bool,
    hybrid: bool,
    revision: str,
    expected_signature: str,
) -> None:
    """The CLI key distinguishes every implemented retrieval configuration."""
    index_path, expected = make_index(tmp_path)
    signatures: list[str] = []

    def cache(
        path: Path,
        queries: list[str],
        k: int,
        signature: str,
        retrieve: object,
    ) -> list[list[MinimalSource]]:
        del retrieve
        assert path == index_path
        assert queries == ["query"]
        assert k == 1
        signatures.append(signature)
        return [[expected]]

    monkeypatch.setattr(cli_module, "cached_retrieval", cache)
    monkeypatch.setattr(
        cli_module,
        "MiniLmEmbedder",
        lambda **kwargs: object(),
    )

    RagCli().search(
        "query",
        k=1,
        index_directory=str(tmp_path),
        semantic=semantic,
        hybrid=hybrid,
        semantic_model_revision=revision,
        cache=True,
    )

    assert signatures == [expected_signature]


def test_search_dataset_deduplicates_and_persists_batch_queries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The batch CLI retrieves one miss and preserves duplicate output rows."""
    index_path, expected = make_index(tmp_path / "index")
    dataset_path = tmp_path / "questions.json"
    dataset_path.write_text(
        '{"rag_questions":['
        '{"question_id":"one","question":"repeat"},'
        '{"question_id":"two","question":"repeat"}]}'
    )
    calls: list[list[str]] = []

    def retrieve(
        path: Path,
        queries: list[str],
        k: int,
        show_progress: bool,
    ) -> list[list[MinimalSource]]:
        assert path == index_path
        assert k == 1
        assert show_progress
        calls.append(queries)
        return [[expected] for _ in queries]

    monkeypatch.setattr(cli_module, "search_lexical_index_batch", retrieve)
    for output_name in ("first", "second"):
        RagCli().search_dataset(
            str(dataset_path),
            k=1,
            index_directory=str(index_path.parent),
            save_directory=str(tmp_path / output_name),
            cache=True,
        )

    assert calls == [["repeat"]]
    assert cache_row_count(index_path) == 1
    assert (tmp_path / "first" / dataset_path.name).read_bytes() == (
        tmp_path / "second" / dataset_path.name
    ).read_bytes()


def test_cache_persists_across_cli_processes_with_identical_output(
    tmp_path: Path,
) -> None:
    """A second process hits SQLite without requiring live FTS postings."""
    index_path, expected = make_index(tmp_path)
    command = [
        sys.executable,
        "-m",
        "src",
        "search",
        "cache",
        "--k=1",
        f"--index_directory={tmp_path}",
        "--cache=True",
    ]
    first = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    with closing(sqlite3.connect(index_path)) as connection:
        connection.execute("DELETE FROM chunks_fts")
        connection.commit()
    second = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    line = (
        f"{expected.file_path} "
        f"[{expected.first_character_index}:{expected.last_character_index}]\n"
    )
    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout == line
    assert first.stderr == second.stderr == ""


class FakeGenerator:
    """Record every generation call while keeping model assets absent."""

    generated: list[str] = []

    @property
    def supported_context_tokens(self) -> int:
        """Return enough room for the tiny fixture prompt."""
        return 200

    def count_prompt_tokens(self, question: str, context: str) -> int:
        """Return a deterministic complete-template size."""
        del question, context
        return 10

    def generate(
        self,
        question: str,
        context: str,
        max_new_tokens: int,
    ) -> str:
        """Record that generation is deliberately never cached."""
        del context, max_new_tokens
        self.generated.append(question)
        return "generated"


def test_answer_caches_only_retrieval_and_generates_every_time(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Answer reuses sources but never stores or reuses generated text."""
    index_path, expected = make_index(tmp_path / "index")
    retrieval_calls = 0

    def search(index: Path, query: str, k: int) -> list[MinimalSource]:
        nonlocal retrieval_calls
        assert index == index_path
        retrieval_calls += 1
        return [expected]

    FakeGenerator.generated.clear()
    monkeypatch.setattr(cli_module, "search_lexical_index", search)
    monkeypatch.setattr(
        cli_module,
        "QwenGenerator",
        lambda **kwargs: FakeGenerator(),
    )
    cli = RagCli()
    for number in (1, 2):
        cli.answer(
            "same answer query",
            k=1,
            index_directory=str(index_path.parent),
            save_path=str(tmp_path / f"answer-{number}.json"),
            token_budget=100,
            max_new_tokens=10,
            cache=True,
        )

    assert retrieval_calls == 1
    assert FakeGenerator.generated == [
        "same answer query",
        "same answer query",
    ]
    assert cache_row_count(index_path) == 1


def test_answer_dataset_has_no_retrieval_cache_surface() -> None:
    """Prior results need neither retrieval nor answer caching."""
    assert "cache" not in inspect.signature(RagCli.answer_dataset).parameters
