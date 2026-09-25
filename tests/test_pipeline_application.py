"""Tests for adapter-neutral pipeline orchestration."""

from __future__ import annotations

from collections.abc import Sequence

from src.application.models import (
    AnswerCommand,
    IndexCommand,
    IndexOperationResult,
    RetrievalCommand,
)
from src.application.ports import TextGenerator
from src.application.use_cases import RagApplication
from src.domain import (
    LexicalIndexMetadata,
    MinimalSource,
    RagDataset,
    UnansweredQuestion,
)


def source(path: str = "corpus/a.md") -> MinimalSource:
    """Build one exact source identity."""
    return MinimalSource(
        file_path=path,
        first_character_index=0,
        last_character_index=4,
    )


class FakeGenerator:
    """Record one adapter-neutral generation call."""

    def __init__(self) -> None:
        self.generated: list[tuple[str, str, int]] = []

    @property
    def supported_context_tokens(self) -> int:
        """Return enough room for the tiny test prompt."""
        return 100

    def count_prompt_tokens(self, question: str, context: str) -> int:
        """Return one deterministic complete-template size."""
        del question, context
        return 10

    def generate(
        self,
        question: str,
        context: str,
        max_new_tokens: int,
    ) -> str:
        """Record and return deterministic generated text."""
        self.generated.append((question, context, max_new_tokens))
        return "grounded"


class FakeOperations:
    """Provide all concrete effects through one fakeable application port."""

    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []
        self.generator = FakeGenerator()

    def index(
        self,
        command: IndexCommand,
        show_progress: bool = False,
    ) -> IndexOperationResult:
        """Record index delegation and return structured metadata."""
        self.calls.append(("index", command, show_progress))
        return IndexOperationResult(
            operation="full",
            metadata=LexicalIndexMetadata(
                corpus_path=command.corpus_path,
                max_chunk_size=command.max_chunk_size,
                document_count=1,
                chunk_count=1,
            ),
            index_directory=command.save_directory,
        )

    def retrieve(
        self,
        command: RetrievalCommand,
        queries: list[str],
        batch: bool = False,
        show_progress: bool = False,
    ) -> list[list[MinimalSource]]:
        """Record single/batch selection and return exact sources."""
        self.calls.append(
            ("retrieve", command, queries, batch, show_progress)
        )
        return [[source(f"corpus/{query}.md")] for query in queries]

    def load_source_texts(
        self,
        index_directory: str,
        sources: Sequence[MinimalSource],
    ) -> list[str]:
        """Record exact hydration order."""
        self.calls.append(("load", index_directory, list(sources)))
        return ["text" for _ in sources]

    def make_generator(
        self,
        command: AnswerCommand,
        show_progress: bool = False,
    ) -> TextGenerator:
        """Record generator construction."""
        self.calls.append(("generator", command, show_progress))
        return self.generator


def index_command() -> IndexCommand:
    """Build a complete shared index command."""
    return IndexCommand(
        max_chunk_size=2000,
        corpus_path="corpus",
        save_directory="processed",
        incremental=False,
        semantic=False,
        semantic_model="model",
        semantic_model_revision="revision",
        semantic_model_cache_directory="models",
        semantic_max_length=256,
        local_files_only=True,
    )


def retrieval_command() -> RetrievalCommand:
    """Build shared retrieval configuration."""
    return RetrievalCommand(k=2, index_directory="processed", cache=True)


def test_index_returns_structured_result_through_shared_port() -> None:
    """Adapters receive data rather than preformatted CLI text."""
    operations = FakeOperations()
    application = RagApplication(operations)
    command = index_command()

    result = application.index(command, show_progress=True)

    assert result.metadata.chunk_count == 1
    assert operations.calls == [("index", command, True)]


def test_single_and_dataset_search_share_retrieval_boundary() -> None:
    """Single and batch adapters differ only in orchestration metadata."""
    operations = FakeOperations()
    application = RagApplication(operations)
    command = retrieval_command()
    dataset = RagDataset(
        rag_questions=[
            UnansweredQuestion(question_id="one", question="first"),
            UnansweredQuestion(question_id="two", question="second"),
        ]
    )

    single = application.search("single", command)
    batch = application.search_dataset(dataset, command, show_progress=True)

    assert single.retrieved_sources == [source("corpus/single.md")]
    assert [
        item.question_id for item in batch.search_results
    ] == ["one", "two"]
    assert batch.k == 2
    assert operations.calls == [
        ("retrieve", command, ["single"], False, False),
        ("retrieve", command, ["first", "second"], True, True),
    ]


def test_answer_reuses_lexical_retrieval_and_always_generates() -> None:
    """Cache retrieval only while always generating answer text."""
    operations = FakeOperations()
    application = RagApplication(operations)
    command = AnswerCommand(
        k=1,
        index_directory="processed",
        model_cache_directory="models",
        token_budget=100,
        max_new_tokens=10,
        local_files_only=True,
        cache=True,
    )

    answer = application.answer("question", command, show_progress=True)

    retrieval_call = operations.calls[0]
    assert retrieval_call[0] == "retrieve"
    retrieval = retrieval_call[1]
    assert isinstance(retrieval, RetrievalCommand)
    assert retrieval.semantic is False
    assert retrieval.hybrid is False
    assert retrieval.cache is True
    assert answer.answer == "grounded"
    assert answer.retrieved_sources == [source("corpus/question.md")]
    assert len(operations.generator.generated) == 1
