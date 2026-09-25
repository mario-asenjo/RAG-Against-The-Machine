"""Shared adapter-neutral index, search, and answer orchestration."""

from __future__ import annotations

from src.application.models import (
    AnswerCommand,
    IndexCommand,
    IndexOperationResult,
    RetrievalCommand,
)
from src.application.ports.pipeline import PipelineOperations
from src.application.use_cases.answer_question import answer_search_result
from src.domain import (
    MinimalAnswer,
    MinimalSearchResults,
    RagDataset,
    StudentSearchResults,
)


class RagApplication:
    """Expose one shared pipeline to CLI and future HTTP adapters."""

    def __init__(self, operations: PipelineOperations) -> None:
        """Bind the application to concrete local operations."""
        self._operations = operations

    def index(
        self,
        command: IndexCommand,
        show_progress: bool = False,
    ) -> IndexOperationResult:
        """Build or update the configured persisted indexes."""
        return self._operations.index(command, show_progress)

    def search(
        self,
        query: str,
        command: RetrievalCommand,
        show_progress: bool = False,
    ) -> MinimalSearchResults:
        """Search one question and return the existing Pydantic contract."""
        sources = self._operations.retrieve(
            command,
            [query],
            batch=False,
            show_progress=show_progress,
        )
        if len(sources) != 1:
            raise RuntimeError("retriever returned an unexpected result count")
        return MinimalSearchResults(
            question=query,
            retrieved_sources=sources[0],
        )

    def search_dataset(
        self,
        dataset: RagDataset,
        command: RetrievalCommand,
        show_progress: bool = False,
    ) -> StudentSearchResults:
        """Search dataset questions through one shared retrieval path."""
        queries = [question.question for question in dataset.rag_questions]
        sources = self._operations.retrieve(
            command,
            queries,
            batch=True,
            show_progress=show_progress,
        )
        if len(sources) != len(dataset.rag_questions):
            raise RuntimeError("retriever returned an unexpected result count")
        return StudentSearchResults(
            search_results=[
                MinimalSearchResults(
                    question_id=question.question_id,
                    question=question.question,
                    retrieved_sources=retrieved_sources,
                )
                for question, retrieved_sources in zip(
                    dataset.rag_questions,
                    sources,
                )
            ],
            k=command.k,
        )

    def answer(
        self,
        query: str,
        command: AnswerCommand,
        show_progress: bool = False,
    ) -> MinimalAnswer:
        """Retrieve lexical sources and generate one grounded answer."""
        retrieval = RetrievalCommand(
            k=command.k,
            index_directory=command.index_directory,
            local_files_only=command.local_files_only,
            cache=command.cache,
        )
        search_result = self.search(query, retrieval, show_progress=False)
        generator = self._operations.make_generator(command, show_progress)
        generation = answer_search_result(
            search_result,
            lambda sources: self._operations.load_source_texts(
                command.index_directory,
                sources,
            ),
            generator,
            token_budget=command.token_budget,
            max_new_tokens=command.max_new_tokens,
        )
        return generation.answer
