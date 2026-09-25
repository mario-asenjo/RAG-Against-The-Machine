"""Python Fire CLI adapter for the RAG application."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import cast

import fire
from tqdm import tqdm

from src.application.models import (
    AnswerCommand,
    IndexCommand,
    IndexOperationResult,
    RetrievalCommand,
    validate_retrieval_mode,
)
from src.application.use_cases import (
    DatasetError,
    EvaluationConfigurationError,
    RagApplication,
    StudentDataError,
    answer_search_result,
    evaluate_search_results,
)
from src.domain import (
    RagDataset,
    StudentSearchResults,
    StudentSearchResultsAndAnswer,
)
from src.infrastructure import (
    INDEX_FILENAME,
    QwenGenerator,
    load_source_texts_from_connection,
)
from src.infrastructure.pipeline import LocalPipelineOperations
from src.infrastructure.semantic import (
    DEFAULT_SEMANTIC_MAX_LENGTH,
    DEFAULT_SEMANTIC_MODEL,
    DEFAULT_SEMANTIC_MODEL_REVISION,
)


def _format_index_result(result: IndexOperationResult) -> str:
    """Preserve the established Fire CLI index status text."""
    semantic_suffix = (
        f"; semantic index {result.semantic_action}"
        if result.semantic_action is not None
        else ""
    )
    if result.operation == "unchanged":
        return (
            f"Index unchanged at {result.index_directory} "
            f"(revision {result.metadata.index_revision})"
            f"{semantic_suffix}"
        )
    if result.operation == "incremental":
        return (
            f"Incrementally indexed {result.metadata.document_count} "
            f"documents at {result.index_directory}: "
            f"{result.added_count} added, "
            f"{result.changed_count} changed, "
            f"{result.deleted_count} deleted, "
            f"revision {result.metadata.index_revision}"
            f"{semantic_suffix}"
        )
    message = (
        f"Indexed {result.metadata.document_count} documents into "
        f"{result.metadata.chunk_count} chunks at {result.index_directory}"
        f"{semantic_suffix}"
    )
    return (
        f"Full rebuild fallback. {message}"
        if result.operation == "fallback"
        else message
    )


class RagCli:
    """Expose project commands as they are implemented issue by issue."""

    def __init__(self) -> None:
        """Bind the Fire adapter to the concrete local application."""
        self._application = RagApplication(LocalPipelineOperations())

    @staticmethod
    def status() -> str:
        """Return the current scaffold status."""
        return (
            "Harness ready. Lexical indexing is implemented; remaining RAG "
            "commands follow the active GitHub issues."
        )

    def index(
        self,
        max_chunk_size: int = 2000,
        corpus_path: str = "data/raw/vllm-0.10.1",
        save_directory: str = "data/processed",
        incremental: bool = False,
        semantic: bool = False,
        semantic_model: str = DEFAULT_SEMANTIC_MODEL,
        semantic_model_revision: str = DEFAULT_SEMANTIC_MODEL_REVISION,
        semantic_model_cache_directory: str = "models/huggingface",
        semantic_max_length: int = DEFAULT_SEMANTIC_MAX_LENGTH,
        local_files_only: bool = False,
    ) -> str:
        """Build canonical BM25 and optionally its semantic projection."""
        try:
            result = self._application.index(
                IndexCommand(
                    max_chunk_size=max_chunk_size,
                    corpus_path=corpus_path,
                    save_directory=save_directory,
                    incremental=incremental,
                    semantic=semantic,
                    semantic_model=semantic_model,
                    semantic_model_revision=semantic_model_revision,
                    semantic_model_cache_directory=(
                        semantic_model_cache_directory
                    ),
                    semantic_max_length=semantic_max_length,
                    local_files_only=local_files_only,
                ),
                show_progress=True,
            )
        except (
            OSError,
            RuntimeError,
            UnicodeError,
            ValueError,
            sqlite3.Error,
        ) as error:
            raise fire.core.FireError(str(error)) from error
        return _format_index_result(result)

    def search(
        self,
        query: str,
        k: int = 10,
        index_directory: str = "data/processed",
        semantic: bool = False,
        hybrid: bool = False,
        semantic_model: str = DEFAULT_SEMANTIC_MODEL,
        semantic_model_revision: str = DEFAULT_SEMANTIC_MODEL_REVISION,
        semantic_model_cache_directory: str = "models/huggingface",
        semantic_max_length: int = DEFAULT_SEMANTIC_MAX_LENGTH,
        local_files_only: bool = False,
        cache: bool = False,
    ) -> str:
        """Return ranked exact source locations from the persisted index."""
        try:
            validate_retrieval_mode(semantic, hybrid)
            result = self._application.search(
                query,
                RetrievalCommand(
                    k=k,
                    index_directory=index_directory,
                    semantic=semantic,
                    hybrid=hybrid,
                    semantic_model=semantic_model,
                    semantic_model_revision=semantic_model_revision,
                    semantic_model_cache_directory=(
                        semantic_model_cache_directory
                    ),
                    semantic_max_length=semantic_max_length,
                    local_files_only=local_files_only,
                    cache=cache,
                ),
            )
        except (OSError, RuntimeError, ValueError) as error:
            raise fire.core.FireError(str(error)) from error
        return "\n".join(
            f"{source.file_path} "
            f"[{source.first_character_index}:{source.last_character_index}]"
            for source in result.retrieved_sources
        )

    def search_dataset(
        self,
        dataset_path: str,
        k: int = 10,
        save_directory: str = "data/output/search_results/UnansweredQuestions",
        index_directory: str = "data/processed",
        semantic: bool = False,
        hybrid: bool = False,
        semantic_model: str = DEFAULT_SEMANTIC_MODEL,
        semantic_model_revision: str = DEFAULT_SEMANTIC_MODEL_REVISION,
        semantic_model_cache_directory: str = "models/huggingface",
        semantic_max_length: int = DEFAULT_SEMANTIC_MAX_LENGTH,
        local_files_only: bool = False,
        cache: bool = False,
    ) -> str:
        """Search a dataset and persist the subject's output model."""
        try:
            validate_retrieval_mode(semantic, hybrid)
            command = RetrievalCommand(
                k=k,
                index_directory=index_directory,
                semantic=semantic,
                hybrid=hybrid,
                semantic_model=semantic_model,
                semantic_model_revision=semantic_model_revision,
                semantic_model_cache_directory=(
                    semantic_model_cache_directory
                ),
                semantic_max_length=semantic_max_length,
                local_files_only=local_files_only,
                cache=cache,
            )
            input_path = Path(dataset_path)
            dataset = RagDataset.model_validate_json(
                input_path.read_text(encoding="utf-8")
            )
            output = self._application.search_dataset(
                dataset,
                command,
                show_progress=True,
            )
            output_directory = Path(save_directory)
            output_directory.mkdir(parents=True, exist_ok=True)
            output_path = output_directory / input_path.name
            output_path.write_text(
                output.model_dump_json(indent=2),
                encoding="utf-8",
            )
        except (OSError, RuntimeError, ValueError) as error:
            raise fire.core.FireError(str(error)) from error
        return f"Saved student_search_results to {output_path.as_posix()}"

    def answer(
        self,
        query: str,
        k: int = 10,
        index_directory: str = "data/processed",
        save_path: str = "data/output/search_results_and_answer/answer.json",
        model_cache_directory: str = "models/huggingface",
        token_budget: int = 2048,
        max_new_tokens: int = 128,
        local_files_only: bool = False,
        cache: bool = False,
    ) -> str:
        """Search once, ground one answer, and save the subject wrapper."""
        try:
            answer = self._application.answer(
                query,
                AnswerCommand(
                    k=k,
                    index_directory=index_directory,
                    model_cache_directory=model_cache_directory,
                    token_budget=token_budget,
                    max_new_tokens=max_new_tokens,
                    local_files_only=local_files_only,
                    cache=cache,
                ),
                show_progress=True,
            )
            output = StudentSearchResultsAndAnswer(
                search_results=[answer],
                k=k,
            )
            output_path = Path(save_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                output.model_dump_json(indent=2),
                encoding="utf-8",
            )
        except (OSError, RuntimeError, ValueError) as error:
            raise fire.core.FireError(str(error)) from error

        sources = "\n".join(
            f"{source.file_path} "
            f"[{source.first_character_index}:{source.last_character_index}]"
            for source in answer.retrieved_sources
        ) or "(none)"
        return (
            f"Answer: {answer.answer}\n"
            f"Sources:\n{sources}\n"
            f"Saved student_search_results_and_answer to "
            f"{output_path.as_posix()}"
        )

    def answer_dataset(
        self,
        student_search_results_path: str,
        save_directory: str = "data/output/search_results_and_answer",
        index_directory: str = "data/processed",
        model_cache_directory: str = "models/huggingface",
        token_budget: int = 2048,
        max_new_tokens: int = 128,
        local_files_only: bool = False,
    ) -> str:
        """Answer prior results sequentially and replace output atomically."""
        input_path = Path(student_search_results_path)
        output_path = Path(save_directory) / input_path.name
        temporary_path = output_path.with_name(f".{output_path.name}.tmp")
        connection: sqlite3.Connection | None = None
        try:
            student = StudentSearchResults.model_validate_json(
                input_path.read_text(encoding="utf-8")
            )
            generator = QwenGenerator(
                cache_directory=Path(model_cache_directory),
                local_files_only=local_files_only,
                show_progress=True,
                progress_position=1,
                progress_leave=False,
            )
            answers = []
            index_path = Path(index_directory) / INDEX_FILENAME
            for search_result in tqdm(
                student.search_results,
                desc="Answering dataset",
                unit="question",
                position=0,
                leave=True,
            ):
                if search_result.retrieved_sources and connection is None:
                    if not index_path.is_file():
                        raise FileNotFoundError(
                            f"Lexical index not found: {index_path}"
                        )
                    connection = sqlite3.connect(index_path)
                generation = answer_search_result(
                    search_result,
                    lambda sources: load_source_texts_from_connection(
                        cast(sqlite3.Connection, connection), sources
                    ),
                    generator,
                    token_budget=token_budget,
                    max_new_tokens=max_new_tokens,
                )
                answers.append(generation.answer)
            output = StudentSearchResultsAndAnswer(
                search_results=answers,
                k=student.k,
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path.unlink(missing_ok=True)
            temporary_path.write_text(
                output.model_dump_json(indent=2),
                encoding="utf-8",
            )
            temporary_path.replace(output_path)
        except (OSError, RuntimeError, ValueError, sqlite3.Error) as error:
            temporary_path.unlink(missing_ok=True)
            raise fire.core.FireError(str(error)) from error
        finally:
            if connection is not None:
                connection.close()

        return (
            "Saved student_search_results_and_answer to "
            f"{output_path.as_posix()}"
        )

    def evaluate(
        self,
        student_search_results_path: str,
        dataset_path: str,
        max_context_length: int = 2000,
    ) -> str:
        """Evaluate student retrieval with macro Recall@1/3/5/10."""
        student_data_is_valid = False
        try:
            student = StudentSearchResults.model_validate_json(
                Path(student_search_results_path).read_text(encoding="utf-8")
            )
        except (OSError, RuntimeError, ValueError) as error:
            raise fire.core.FireError(
                f"Student data is valid: {student_data_is_valid}\n{error}"
            ) from error

        try:
            dataset = RagDataset.model_validate_json(
                Path(dataset_path).read_text(encoding="utf-8")
            )
        except (OSError, RuntimeError, ValueError) as error:
            raise fire.core.FireError(
                f"Dataset is valid: False\n{error}"
            ) from error

        try:
            evaluation = evaluate_search_results(
                student,
                dataset,
                max_context_length=max_context_length,
            )
        except StudentDataError as error:
            raise fire.core.FireError(
                f"Student data is valid: {student_data_is_valid}\n{error}"
            ) from error
        except DatasetError as error:
            raise fire.core.FireError(
                f"Dataset is valid: False\n{error}"
            ) from error
        except EvaluationConfigurationError as error:
            raise fire.core.FireError(
                f"Configuration error: {error}"
            ) from error
        student_data_is_valid = True

        metrics = {
            f"recall@{k}": recall
            for k, recall in evaluation.recall_at.items()
        }
        metric_lines = "\n".join(
            f"Recall@{k}: {recall:.3f} ({recall * 100:.1f}%)"
            for k, recall in evaluation.recall_at.items()
        )
        return (
            f"Student data is valid: {student_data_is_valid}\n"
            f"Total number of questions: {evaluation.total_questions}\n"
            "Total number of questions with sources: "
            f"{evaluation.questions_evaluated}\n"
            "Total number of questions with student sources: "
            f"{evaluation.questions_with_student_sources}\n\n"
            "Evaluation Results\n"
            "========================================\n"
            f"Questions evaluated: {evaluation.questions_evaluated}\n"
            f"{metric_lines}\n"
            f"{metrics}"
        )


def main() -> None:
    """Run the Python Fire command-line application."""
    fire.Fire(RagCli)
