"""Python Fire CLI adapter for the RAG application."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import cast

import fire
from tqdm import tqdm

from src.application.ports import Chunker
from src.application.use_cases import (
    DatasetError,
    EvaluationConfigurationError,
    StudentDataError,
    answer_search_result,
    build_lexical_index,
    evaluate_search_results,
    plan_lexical_index_update,
)
from src.chunking import chunk_python_document, chunk_text_document
from src.domain import (
    MinimalSearchResults,
    RagDataset,
    StudentSearchResults,
    StudentSearchResultsAndAnswer,
)
from src.infrastructure import (
    INDEX_FILENAME,
    QwenGenerator,
    load_corpus,
    load_index_chunks,
    load_index_metadata,
    load_index_state,
    load_source_texts,
    load_source_texts_from_connection,
    save_lexical_index,
    search_lexical_index,
    search_lexical_index_batch,
    update_lexical_index,
)
from src.infrastructure.semantic import (
    DEFAULT_SEMANTIC_MAX_LENGTH,
    DEFAULT_SEMANTIC_MODEL,
    DEFAULT_SEMANTIC_MODEL_REVISION,
    SEMANTIC_INDEX_FILENAME,
    MiniLmEmbedder,
    build_semantic_index,
    ensure_semantic_index,
    load_semantic_index,
    search_semantic_index,
    search_semantic_index_batch,
    update_semantic_index,
)


class RagCli:
    """Expose project commands as they are implemented issue by issue."""

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
        chunkers: dict[str, Chunker] = {
            ".md": chunk_text_document,
            ".py": chunk_python_document,
            ".txt": chunk_text_document,
        }
        try:
            corpus_root = Path(corpus_path)
            documents = load_corpus(corpus_root, show_progress=True)
            index_path = Path(save_directory) / INDEX_FILENAME
            semantic_path = Path(save_directory) / SEMANTIC_INDEX_FILENAME
            fallback = False
            previous_revision = 0
            if incremental:
                try:
                    previous_revision = load_index_metadata(
                        index_path
                    ).index_revision
                    current, existing_files, existing_counts = (
                        load_index_state(index_path)
                    )
                    if current.corpus_path != corpus_root.as_posix():
                        raise ValueError("indexed corpus path has changed")
                    if current.max_chunk_size != max_chunk_size:
                        raise ValueError("indexed max_chunk_size has changed")
                    existing_chunks = load_index_chunks(index_path)
                    update = plan_lexical_index_update(
                        documents,
                        existing_files,
                        existing_counts,
                        existing_chunks,
                        chunkers,
                        corpus_root.as_posix(),
                        max_chunk_size,
                        current.index_revision,
                        show_progress=True,
                    )
                except (OSError, RuntimeError, ValueError, sqlite3.Error):
                    fallback = True
                else:
                    if not update.has_changes:
                        lexical_result = (
                            "Index unchanged at "
                            f"{index_path.parent.as_posix()} "
                            f"(revision {current.index_revision})"
                        )
                        if not semantic:
                            return lexical_result
                        embedder = MiniLmEmbedder(
                            cache_directory=Path(
                                semantic_model_cache_directory
                            ),
                            model_name=semantic_model,
                            model_revision=semantic_model_revision,
                            max_length=semantic_max_length,
                            local_files_only=local_files_only,
                            show_progress=True,
                        )
                        rebuilt = ensure_semantic_index(
                            existing_chunks,
                            semantic_path,
                            current.index_revision,
                            embedder,
                        )
                        action = "rebuilt" if rebuilt else "unchanged"
                        return f"{lexical_result}; semantic index {action}"

                    existing_paths = {
                        item.file_path for item in existing_files
                    }
                    added = sum(
                        path not in existing_paths
                        for path in update.changed_paths
                    )
                    changed = len(update.changed_paths) - added
                    semantic_compatible = False
                    if semantic:
                        embedder = MiniLmEmbedder(
                            cache_directory=Path(
                                semantic_model_cache_directory
                            ),
                            model_name=semantic_model,
                            model_revision=semantic_model_revision,
                            max_length=semantic_max_length,
                            local_files_only=local_files_only,
                            show_progress=True,
                        )
                        try:
                            load_semantic_index(
                                semantic_path,
                                expected_source_index_revision=(
                                    current.index_revision
                                ),
                                expected_model_name=embedder.model_name,
                                expected_model_revision=(
                                    embedder.model_revision
                                ),
                                expected_max_length=embedder.max_length,
                                canonical_chunks=existing_chunks,
                            )
                        except (OSError, RuntimeError, ValueError):
                            pass
                        else:
                            semantic_compatible = True

                    update_lexical_index(update, index_path)
                    semantic_result = ""
                    if semantic:
                        canonical_chunks = load_index_chunks(index_path)
                        if semantic_compatible:
                            update_semantic_index(
                                semantic_path,
                                existing_chunks,
                                canonical_chunks,
                                update,
                                embedder,
                            )
                            semantic_result = "; semantic index updated"
                        else:
                            build_semantic_index(
                                canonical_chunks,
                                semantic_path,
                                update.metadata.index_revision,
                                embedder,
                            )
                            semantic_result = "; semantic index rebuilt"
                    return (
                        f"Incrementally indexed {len(update.files)} documents "
                        f"at {index_path.parent.as_posix()}: "
                        f"{added} added, {changed} changed, "
                        f"{len(update.removed_paths)} deleted, "
                        f"revision {update.metadata.index_revision}"
                        f"{semantic_result}"
                    )

            index_revision = previous_revision + 1 if previous_revision else 1
            if not fallback:
                try:
                    current, _, _ = load_index_state(index_path)
                    index_revision = current.index_revision + 1
                except (OSError, RuntimeError, ValueError, sqlite3.Error):
                    pass
            if semantic:
                try:
                    semantic_metadata, _, _ = load_semantic_index(
                        semantic_path
                    )
                    index_revision = max(
                        index_revision,
                        semantic_metadata.source_index_revision + 1,
                    )
                except (OSError, RuntimeError, ValueError):
                    pass
            build = build_lexical_index(
                documents,
                chunkers,
                corpus_root.as_posix(),
                max_chunk_size,
                show_progress=True,
                index_revision=index_revision,
            )
            index_path = save_lexical_index(
                build,
                index_path,
                show_progress=True,
            )
            if semantic:
                embedder = MiniLmEmbedder(
                    cache_directory=Path(semantic_model_cache_directory),
                    model_name=semantic_model,
                    model_revision=semantic_model_revision,
                    max_length=semantic_max_length,
                    local_files_only=local_files_only,
                    show_progress=True,
                )
                build_semantic_index(
                    load_index_chunks(index_path),
                    semantic_path,
                    build.metadata.index_revision,
                    embedder,
                )
            else:
                semantic_path.unlink(missing_ok=True)
        except (
            OSError,
            RuntimeError,
            UnicodeError,
            ValueError,
            sqlite3.Error,
        ) as error:
            raise fire.core.FireError(str(error)) from error

        result = (
            f"Indexed {build.metadata.document_count} documents into "
            f"{build.metadata.chunk_count} chunks at "
            f"{index_path.parent.as_posix()}"
        )
        if semantic:
            result = f"{result}; semantic index built"
        return f"Full rebuild fallback. {result}" if fallback else result

    def search(
        self,
        query: str,
        k: int = 10,
        index_directory: str = "data/processed",
        semantic: bool = False,
        semantic_model: str = DEFAULT_SEMANTIC_MODEL,
        semantic_model_revision: str = DEFAULT_SEMANTIC_MODEL_REVISION,
        semantic_model_cache_directory: str = "models/huggingface",
        semantic_max_length: int = DEFAULT_SEMANTIC_MAX_LENGTH,
        local_files_only: bool = False,
    ) -> str:
        """Return ranked exact source locations from the persisted index."""
        try:
            lexical_path = Path(index_directory) / INDEX_FILENAME
            if semantic:
                embedder = MiniLmEmbedder(
                    cache_directory=Path(semantic_model_cache_directory),
                    model_name=semantic_model,
                    model_revision=semantic_model_revision,
                    max_length=semantic_max_length,
                    local_files_only=local_files_only,
                )
                sources = search_semantic_index(
                    Path(index_directory) / SEMANTIC_INDEX_FILENAME,
                    lexical_path,
                    query,
                    k,
                    embedder,
                )
            else:
                sources = search_lexical_index(lexical_path, query, k)
        except (OSError, RuntimeError, ValueError) as error:
            raise fire.core.FireError(str(error)) from error
        return "\n".join(
            f"{source.file_path} "
            f"[{source.first_character_index}:{source.last_character_index}]"
            for source in sources
        )

    def search_dataset(
        self,
        dataset_path: str,
        k: int = 10,
        save_directory: str = "data/output/search_results/UnansweredQuestions",
        index_directory: str = "data/processed",
        semantic: bool = False,
        semantic_model: str = DEFAULT_SEMANTIC_MODEL,
        semantic_model_revision: str = DEFAULT_SEMANTIC_MODEL_REVISION,
        semantic_model_cache_directory: str = "models/huggingface",
        semantic_max_length: int = DEFAULT_SEMANTIC_MAX_LENGTH,
        local_files_only: bool = False,
    ) -> str:
        """Search a dataset and persist the subject's output model."""
        try:
            input_path = Path(dataset_path)
            dataset = RagDataset.model_validate_json(
                input_path.read_text(encoding="utf-8")
            )
            queries = [question.question for question in dataset.rag_questions]
            lexical_path = Path(index_directory) / INDEX_FILENAME
            if semantic:
                embedder = MiniLmEmbedder(
                    cache_directory=Path(semantic_model_cache_directory),
                    model_name=semantic_model,
                    model_revision=semantic_model_revision,
                    max_length=semantic_max_length,
                    local_files_only=local_files_only,
                    show_progress=True,
                )
                sources = search_semantic_index_batch(
                    Path(index_directory) / SEMANTIC_INDEX_FILENAME,
                    lexical_path,
                    queries,
                    k,
                    embedder,
                    show_progress=True,
                )
            else:
                sources = search_lexical_index_batch(
                    lexical_path,
                    queries,
                    k,
                    show_progress=True,
                )
            output = StudentSearchResults(
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
                k=k,
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
    ) -> str:
        """Search once, ground one answer, and save the subject wrapper."""
        try:
            index_path = Path(index_directory) / INDEX_FILENAME
            search_result = MinimalSearchResults(
                question=query,
                retrieved_sources=search_lexical_index(index_path, query, k),
            )
            generator = QwenGenerator(
                cache_directory=Path(model_cache_directory),
                local_files_only=local_files_only,
                show_progress=True,
            )
            generation = answer_search_result(
                search_result,
                lambda sources: load_source_texts(index_path, sources),
                generator,
                token_budget=token_budget,
                max_new_tokens=max_new_tokens,
            )
            output = StudentSearchResultsAndAnswer(
                search_results=[generation.answer],
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
            for source in generation.answer.retrieved_sources
        ) or "(none)"
        return (
            f"Answer: {generation.answer.answer}\n"
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
