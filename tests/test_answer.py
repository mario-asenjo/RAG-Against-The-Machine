"""Tests for exact-source grounded single-query answers."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Sequence

import pytest
from fire.core import FireError

from src.adapters import cli as cli_module
from src.adapters.cli import RagCli
from src.application.use_cases.answer_question import (
    ABSTENTION_ANSWER,
    answer_search_result,
)
from src.domain import (
    LexicalIndexBuild,
    LexicalIndexMetadata,
    MinimalSearchResults,
    MinimalSource,
    SourceChunk,
    StudentSearchResultsAndAnswer,
)
from src.infrastructure.generation import QwenGenerator, supported_context
from src.infrastructure.index import load_source_texts, save_lexical_index

ROOT = Path(__file__).resolve().parents[1]


class FakeGenerator:
    """Record application calls without loading a model."""

    def __init__(
        self,
        token_counts: dict[str, int] | None = None,
        supported_tokens: int = 40960,
        answer: str = "Grounded answer.",
    ) -> None:
        self.token_counts = token_counts or {"": 10}
        self.supported_tokens = supported_tokens
        self.answer = answer
        self.counted_contexts: list[str] = []
        self.generated: list[tuple[str, str, int]] = []

    @property
    def supported_context_tokens(self) -> int:
        """Return a deterministic fake model capacity."""
        return self.supported_tokens

    def count_prompt_tokens(self, question: str, context: str) -> int:
        """Record and return the configured full-template token count."""
        del question
        self.counted_contexts.append(context)
        return self.token_counts[context]

    def generate(
        self,
        question: str,
        context: str,
        max_new_tokens: int,
    ) -> str:
        """Record generation inputs and return fixed text."""
        self.generated.append((question, context, max_new_tokens))
        return self.answer


def source(
    path: str,
    first: int,
    last: int,
) -> MinimalSource:
    """Build one exact persisted-source identity."""
    return MinimalSource(
        file_path=path,
        first_character_index=first,
        last_character_index=last,
    )


def make_answer_index(tmp_path: Path) -> tuple[Path, list[SourceChunk]]:
    """Persist chunks sharing paths but not exact offsets."""
    chunks = [
        SourceChunk(
            file_path="data/raw/vllm-0.10.1/docs/guide.md",
            first_character_index=0,
            last_character_index=5,
            chunk_type="text",
            text="first",
        ),
        SourceChunk(
            file_path="data/raw/vllm-0.10.1/docs/guide.md",
            first_character_index=10,
            last_character_index=16,
            chunk_type="text",
            text="second",
        ),
        SourceChunk(
            file_path="data/raw/vllm-0.10.1/vllm/core.py",
            first_character_index=20,
            last_character_index=25,
            chunk_type="python",
            text="third",
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
    return save_lexical_index(
        build, tmp_path / "lexical_index.sqlite3"
    ), chunks


def test_load_source_texts_matches_all_fields_in_received_order(
    tmp_path: Path,
) -> None:
    """Source hydration must not collapse paths or reorder ranked spans."""
    index_path, chunks = make_answer_index(tmp_path)
    requested = [chunks[1], chunks[0], chunks[1]]

    texts = load_source_texts(index_path, requested)

    assert texts == ["second", "first", "second"]


def test_load_source_texts_rejects_missing_exact_span(tmp_path: Path) -> None:
    """A nearby chunk is never a substitute for an absent exact identity."""
    index_path, _ = make_answer_index(tmp_path)

    with pytest.raises(ValueError, match="Exact source not found"):
        load_source_texts(
            index_path,
            [source("data/raw/vllm-0.10.1/docs/guide.md", 0, 4)],
        )


def test_answer_uses_ranked_prefix_and_preserves_sources() -> None:
    """Budgeting may omit context but never mutate retrieved metadata."""
    first = source("first.py", 0, 5)
    second = source("second.py", 10, 16)
    third = source("third.py", 20, 25)
    search = MinimalSearchResults(
        question_id="q1",
        question="What is supported?",
        retrieved_sources=[first, second, third],
    )
    first_context = "[Source 1: first.py [0:5]]\nalpha"
    both_context = (
        f"{first_context}\n\n[Source 2: second.py [10:16]]\nbeta"
    )
    first_and_third = (
        f"{first_context}\n\n[Source 3: third.py [20:25]]\ngamma"
    )
    generator = FakeGenerator(
        token_counts={
            "": 10,
            first_context: 30,
            both_context: 60,
            first_and_third: 30,
        }
    )
    loaded_sources: list[MinimalSource] = []

    def load_all(sources: Sequence[MinimalSource]) -> list[str]:
        loaded_sources.extend(sources)
        return ["alpha", "beta", "gamma"]

    result = answer_search_result(
        search,
        load_all,
        generator,
        token_budget=50,
        max_new_tokens=10,
    )

    assert loaded_sources == [first, second, third]
    assert result.included_sources == (first,)
    assert result.answer.question_id == "q1"
    assert result.answer.question == search.question
    assert result.answer.retrieved_sources == [first, second, third]
    assert result.answer.answer == "Grounded answer."
    assert generator.counted_contexts == ["", first_context, both_context]
    assert generator.generated == [(search.question, first_context, 10)]


def test_answer_rejects_stale_source_outside_fitted_prefix(
    tmp_path: Path,
) -> None:
    """Every retrieved tuple is validated even if its text would not fit."""
    index_path, chunks = make_answer_index(tmp_path)
    first = chunks[0]
    missing = source(first.file_path, 10, 15)
    search = MinimalSearchResults(
        question="question",
        retrieved_sources=[first, missing],
    )
    first_context = (
        "[Source 1: data/raw/vllm-0.10.1/docs/guide.md [0:5]]\nfirst"
    )
    generator = FakeGenerator(
        token_counts={"": 10, first_context: 30}
    )

    with pytest.raises(ValueError, match="Exact source not found"):
        answer_search_result(
            search,
            lambda sources: load_source_texts(index_path, sources),
            generator,
            token_budget=50,
            max_new_tokens=10,
        )

    assert generator.generated == []


@pytest.mark.parametrize(
    ("token_budget", "max_new_tokens", "supported", "message"),
    [
        (100, 10, 99, "supported context"),
        (100, 0, 40960, "max_new_tokens must be positive"),
        (100, -1, 40960, "max_new_tokens must be positive"),
        (100, 100, 40960, "smaller than token_budget"),
    ],
)
def test_answer_rejects_invalid_runtime_budget(
    token_budget: int,
    max_new_tokens: int,
    supported: int,
    message: str,
) -> None:
    """Every D-0009 budget guard must fail before generation."""
    item = source("file.py", 0, 1)
    search = MinimalSearchResults(
        question="question",
        retrieved_sources=[item],
    )
    generator = FakeGenerator(supported_tokens=supported)

    with pytest.raises(ValueError, match=message):
        answer_search_result(
            search,
            lambda sources: ["x"],
            generator,
            token_budget=token_budget,
            max_new_tokens=max_new_tokens,
        )

    assert generator.generated == []


def test_answer_rejects_whitespace_generator_output() -> None:
    """Empty model text is a technical failure, never a valid answer."""
    item = source("file.py", 0, 1)
    context = "[Source 1: file.py [0:1]]\nx"
    search = MinimalSearchResults(
        question="question",
        retrieved_sources=[item],
    )
    generator = FakeGenerator(
        token_counts={"": 10, context: 20},
        answer="  \n",
    )

    with pytest.raises(RuntimeError, match="empty answer"):
        answer_search_result(
            search,
            lambda sources: ["x"],
            generator,
            token_budget=100,
            max_new_tokens=10,
        )

    assert generator.generated == [("question", context, 10)]


def test_answer_rejects_base_prompt_before_loading_sources() -> None:
    """Base prompt overflow fails before source I/O and generation."""
    search = MinimalSearchResults(
        question="very long question",
        retrieved_sources=[source("file.py", 0, 1)],
    )
    generator = FakeGenerator(token_counts={"": 41})
    loaded = False

    def loader(sources: Sequence[MinimalSource]) -> list[str]:
        """Expose accidental source loading after known prompt overflow."""
        nonlocal loaded
        loaded = True
        return ["x" for _ in sources]

    with pytest.raises(ValueError, match="question and instructions"):
        answer_search_result(
            search,
            loader,
            generator,
            token_budget=50,
            max_new_tokens=10,
        )

    assert not loaded
    assert generator.generated == []


def test_answer_rejects_when_no_complete_fragment_fits() -> None:
    """Retrieved evidence that cannot fit is a budget error, not abstention."""
    item = source("file.py", 0, 1)
    search = MinimalSearchResults(
        question="question", retrieved_sources=[item]
    )
    context = "[Source 1: file.py [0:1]]\nx"
    generator = FakeGenerator(token_counts={"": 10, context: 41})

    with pytest.raises(ValueError, match="No complete source"):
        answer_search_result(
            search,
            lambda sources: ["x"],
            generator,
            token_budget=50,
            max_new_tokens=10,
        )

    assert generator.generated == []


def test_answer_abstains_without_source_io_or_generator() -> None:
    """k=0/no matches must not initialize tokenizer/model work."""
    search = MinimalSearchResults(question="question", retrieved_sources=[])
    generator = FakeGenerator()
    loaded = False

    def loader(sources: Sequence[MinimalSource]) -> list[str]:
        """Expose accidental hydration for empty retrieval."""
        nonlocal loaded
        loaded = True
        return []

    result = answer_search_result(search, loader, generator)

    assert result.answer.answer == ABSTENTION_ANSWER
    assert result.answer.retrieved_sources == []
    assert result.included_sources == ()
    assert not loaded
    assert generator.counted_contexts == []
    assert generator.generated == []


@pytest.mark.parametrize(
    ("model_limit", "tokenizer_limit", "expected"),
    [
        (40960, 131072, 40960),
        (40960, 8192, 8192),
        (40960, 10**30, 40960),
        (40960, None, 40960),
    ],
)
def test_supported_context_uses_only_valid_finite_limits(
    model_limit: int,
    tokenizer_limit: object,
    expected: int,
) -> None:
    """Tokenizer sentinels cannot raise model capacity."""
    assert supported_context(model_limit, tokenizer_limit) == expected


def test_qwen_token_count_uses_question_context_and_no_thinking(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The real adapter must count a grounded no-thinking chat template."""
    import transformers

    class RecordingTokenizer:
        """Capture the adapter's template request without model assets."""

        def __init__(self) -> None:
            self.messages: list[dict[str, str]] = []
            self.options: dict[str, object] = {}

        def apply_chat_template(
            self,
            messages: list[dict[str, str]],
            **options: object,
        ) -> list[int]:
            self.messages = messages
            self.options = options
            return [1, 2, 3]

    tokenizer = RecordingTokenizer()
    monkeypatch.setattr(
        transformers.AutoConfig,
        "from_pretrained",
        lambda *args, **kwargs: SimpleNamespace(max_position_embeddings=40960),
    )
    monkeypatch.setattr(
        transformers.AutoTokenizer,
        "from_pretrained",
        lambda *args, **kwargs: tokenizer,
    )
    generator = QwenGenerator(
        Path("unused"), local_files_only=True, show_progress=True
    )

    count = generator.count_prompt_tokens("question text", "evidence text")

    assert count == 3
    assert tokenizer.messages[0]["role"] == "system"
    assert "only the supplied context" in tokenizer.messages[0]["content"]
    assert tokenizer.messages[1] == {
        "role": "user",
        "content": "Context:\nevidence text\n\nQuestion:\nquestion text",
    }
    assert tokenizer.options == {
        "tokenize": True,
        "add_generation_prompt": True,
        "enable_thinking": False,
    }
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Loading Qwen tokenizer" in captured.err


def test_qwen_generation_reuses_grounded_no_thinking_template(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Generation must use the same grounded template contract as counting."""
    import torch
    import transformers

    class RecordingTokenizer:
        """Return tensor inputs and capture generation template options."""

        eos_token_id = 0
        model_max_length = 131072

        def __init__(self) -> None:
            self.messages: list[dict[str, str]] = []
            self.options: dict[str, object] = {}

        def apply_chat_template(
            self,
            messages: list[dict[str, str]],
            **options: object,
        ) -> dict[str, Any]:
            self.messages = messages
            self.options = options
            return {"input_ids": torch.tensor([[1, 2, 3]])}

        def decode(
            self,
            token_ids: Any,
            skip_special_tokens: bool,
        ) -> str:
            assert token_ids.tolist() == [4]
            assert skip_special_tokens
            return "generated answer"

    class RecordingModel:
        """Append one token and record deterministic decoding options."""

        def __init__(self) -> None:
            self.options: dict[str, Any] = {}

        def generate(self, **options: Any) -> Any:
            self.options = options
            return torch.tensor([[1, 2, 3, 4]])

        def eval(self) -> RecordingModel:
            return self

    tokenizer = RecordingTokenizer()
    model = RecordingModel()
    generator = QwenGenerator(
        Path("unused"), local_files_only=True, show_progress=True
    )
    generator._config = SimpleNamespace(max_position_embeddings=40960)
    generator._tokenizer = tokenizer
    monkeypatch.setattr(
        transformers.AutoModelForCausalLM,
        "from_pretrained",
        lambda *args, **kwargs: model,
    )

    answer = generator.generate("question text", "evidence text", 8)

    assert answer == "generated answer"
    assert tokenizer.messages[1] == {
        "role": "user",
        "content": "Context:\nevidence text\n\nQuestion:\nquestion text",
    }
    assert tokenizer.options == {
        "tokenize": True,
        "add_generation_prompt": True,
        "enable_thinking": False,
        "return_dict": True,
        "return_tensors": "pt",
    }
    assert model.options["max_new_tokens"] == 8
    assert model.options["do_sample"] is False
    assert model.options["temperature"] is None
    assert model.options["top_p"] is None
    assert model.options["top_k"] is None
    captured = capsys.readouterr()
    assert captured.out == ""
    progress = captured.err
    assert progress.index("Loading Qwen model") < progress.index(
        "Generating answer"
    )


def test_supported_context_rejects_boolean_capacity() -> None:
    """Python booleans are integers but never token capacities."""
    with pytest.raises(ValueError, match="model context"):
        supported_context(True, 8192)


def test_answer_cli_searches_once_and_saves_pydantic_wrapper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The CLI composes one search with the shared application path."""
    exact = source("file.py", 0, 4)
    calls: list[tuple[Path, str, int]] = []

    def search_once(path: Path, query: str, k: int) -> list[MinimalSource]:
        calls.append((path, query, k))
        return [exact]

    fake = FakeGenerator(
        token_counts={
            "": 10,
            "[Source 1: file.py [0:4]]\ntext": 20,
        }
    )
    monkeypatch.setattr(cli_module, "search_lexical_index", search_once)
    monkeypatch.setattr(
        cli_module, "load_source_texts", lambda path, sources: ["text"]
    )
    generator_options: list[dict[str, object]] = []

    def make_generator(**kwargs: object) -> FakeGenerator:
        generator_options.append(kwargs)
        return fake

    monkeypatch.setattr(cli_module, "QwenGenerator", make_generator)
    output_path = tmp_path / "answer.json"

    displayed = RagCli().answer(
        "What?",
        k=1,
        index_directory=str(tmp_path / "index"),
        save_path=str(output_path),
        token_budget=100,
        max_new_tokens=10,
    )

    assert calls == [
        (tmp_path / "index" / "lexical_index.sqlite3", "What?", 1)
    ]
    assert generator_options == [
        {
            "cache_directory": Path("models/huggingface"),
            "local_files_only": False,
            "show_progress": True,
        }
    ]
    output = StudentSearchResultsAndAnswer.model_validate_json(
        output_path.read_text(encoding="utf-8")
    )
    assert output.k == 1
    assert output.search_results[0].retrieved_sources == [exact]
    assert output.search_results[0].answer == "Grounded answer."
    assert "Answer: Grounded answer." in displayed
    assert "file.py [0:4]" in displayed
    assert output_path.as_posix() in displayed.replace("\\", "/")


def run_answer(
    index_directory: Path,
    output_path: Path,
    query: str = "vLLM",
    k: int = 0,
    extra: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run answer through the evaluator-facing Fire boundary."""
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "src",
            "answer",
            query,
            f"--k={k}",
            f"--index_directory={index_directory}",
            f"--save_path={output_path}",
            "--model_cache_directory=definitely-missing-model-cache",
            "--local_files_only=True",
            *(extra or []),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    ("query", "k"),
    [("vLLM", 0), ("unfindabletoken", 10)],
)
def test_answer_cli_abstains_with_valid_json_without_model_cache(
    tmp_path: Path,
    query: str,
    k: int,
) -> None:
    """Zero/empty retrieval writes an abstention without model assets."""
    index_path, _ = make_answer_index(tmp_path / "index")
    output_path = tmp_path / "answer.json"

    completed = run_answer(index_path.parent, output_path, query, k)

    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""
    assert "Answer: " + ABSTENTION_ANSWER in completed.stdout
    output = StudentSearchResultsAndAnswer.model_validate_json(
        output_path.read_text(encoding="utf-8")
    )
    assert output.k == k
    assert output.search_results[0].retrieved_sources == []
    assert output.search_results[0].answer == ABSTENTION_ANSWER


def test_answer_cli_reports_missing_model_cache_without_traceback(
    tmp_path: Path,
) -> None:
    """Evidence plus absent model assets is a technical failure."""
    index_path, _ = make_answer_index(tmp_path / "index")

    completed = run_answer(
        index_path.parent,
        tmp_path / "answer.json",
        query="first",
        k=1,
    )

    assert completed.returncode != 0
    assert completed.stdout == ""
    assert "Could not load Qwen tokenizer" in completed.stderr
    assert "Traceback" not in completed.stderr
    assert not (tmp_path / "answer.json").exists()


@pytest.mark.parametrize(
    ("kind", "message"),
    [
        ("empty_query", "searchable terms"),
        ("missing_index", "Lexical index not found"),
        ("corrupt_index", "Could not search lexical index"),
        ("invalid_budget", "token_budget must be positive"),
    ],
)
def test_answer_cli_translates_input_and_technical_failures(
    tmp_path: Path,
    kind: str,
    message: str,
) -> None:
    """Known boundary failures are non-zero and traceback-free."""
    index_directory = tmp_path / "index"
    query = "vLLM"
    extra: list[str] = []
    if kind == "empty_query":
        make_answer_index(index_directory)
        query = ""
    elif kind == "corrupt_index":
        index_directory.mkdir()
        (index_directory / "lexical_index.sqlite3").write_text(
            "not sqlite", encoding="utf-8"
        )
    elif kind == "invalid_budget":
        make_answer_index(index_directory)
        extra = ["--token_budget=0"]
    completed = run_answer(
        index_directory, tmp_path / "answer.json", query, 0, extra
    )

    assert completed.returncode != 0
    assert completed.stdout == ""
    assert message in completed.stderr
    assert "Traceback" not in completed.stderr


def test_answer_cli_reports_missing_exact_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stale retrieval metadata fails instead of using nearby text."""
    index_path, _ = make_answer_index(tmp_path / "index")
    missing = source(
        "data/raw/vllm-0.10.1/docs/guide.md",
        0,
        4,
    )
    fake = FakeGenerator(token_counts={"": 10})
    monkeypatch.setattr(
        cli_module, "search_lexical_index", lambda *args: [missing]
    )
    monkeypatch.setattr(cli_module, "QwenGenerator", lambda **kwargs: fake)
    output_path = tmp_path / "answer.json"

    with pytest.raises(FireError, match="Exact source not found"):
        RagCli().answer(
            "What?",
            index_directory=str(index_path.parent),
            save_path=str(output_path),
            token_budget=100,
            max_new_tokens=10,
        )

    assert not output_path.exists()
    assert fake.generated == []


def test_answer_cli_translates_generator_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Model failures remain technical errors instead of abstentions."""
    exact = source("file.py", 0, 4)

    class FailingGenerator(FakeGenerator):
        """Raise the technical model error at generation time."""

        def generate(
            self,
            question: str,
            context: str,
            max_new_tokens: int,
        ) -> str:
            raise RuntimeError("model unavailable")

    fake = FailingGenerator(
        token_counts={
            "": 10,
            "[Source 1: file.py [0:4]]\ntext": 20,
        }
    )
    monkeypatch.setattr(
        cli_module, "search_lexical_index", lambda *args: [exact]
    )
    monkeypatch.setattr(
        cli_module, "load_source_texts", lambda *args: ["text"]
    )
    monkeypatch.setattr(cli_module, "QwenGenerator", lambda **kwargs: fake)

    with pytest.raises(FireError, match="model unavailable"):
        RagCli().answer("What?", save_path=str(tmp_path / "answer.json"))

    assert not (tmp_path / "answer.json").exists()
