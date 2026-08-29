"""Python Fire CLI adapter for the RAG application."""

from __future__ import annotations

from pathlib import Path
from typing import NoReturn

import fire

from src.application.ports import Chunker
from src.application.use_cases import build_lexical_index
from src.chunking import chunk_python_document, chunk_text_document
from src.domain import MinimalSearchResults, RagDataset, StudentSearchResults
from src.infrastructure import (
    INDEX_FILENAME,
    load_corpus,
    save_lexical_index,
    search_lexical_index,
    search_lexical_index_batch,
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

    @staticmethod
    def _not_implemented(command: str) -> NoReturn:
        """Fail gracefully for a command whose implementation is pending."""
        raise fire.core.FireError(
            f"'{command}' is not implemented yet. "
        )

    def index(
        self,
        max_chunk_size: int = 2000,
        corpus_path: str = "data/raw/vllm-0.10.1",
        save_directory: str = "data/processed",
    ) -> str:
        """Build and atomically persist the SQLite FTS5 BM25 index."""
        chunkers: dict[str, Chunker] = {
            ".md": chunk_text_document,
            ".py": chunk_python_document,
            ".txt": chunk_text_document,
        }
        try:
            corpus_root = Path(corpus_path)
            documents = load_corpus(corpus_root, show_progress=True)
            build = build_lexical_index(
                documents,
                chunkers,
                corpus_root.as_posix(),
                max_chunk_size,
                show_progress=True,
            )
            index_path = save_lexical_index(
                build,
                Path(save_directory) / INDEX_FILENAME,
                show_progress=True,
            )
        except (OSError, RuntimeError, UnicodeError, ValueError) as error:
            raise fire.core.FireError(str(error)) from error

        return (
            f"Indexed {build.metadata.document_count} documents into "
            f"{build.metadata.chunk_count} chunks at "
            f"{index_path.parent.as_posix()}"
        )

    def search(
        self,
        query: str,
        k: int = 10,
        index_directory: str = "data/processed",
    ) -> str:
        """Return ranked exact source locations from the persisted index."""
        try:
            sources = search_lexical_index(
                Path(index_directory) / INDEX_FILENAME,
                query,
                k,
            )
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
        save_directory: str = "data/output/search_results",
        index_directory: str = "data/processed",
    ) -> str:
        """Search a dataset and persist the subject's output model."""
        try:
            input_path = Path(dataset_path)
            dataset = RagDataset.model_validate_json(
                input_path.read_text(encoding="utf-8")
            )
            sources = search_lexical_index_batch(
                Path(index_directory) / INDEX_FILENAME,
                [question.question for question in dataset.rag_questions],
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

    def answer(self, query: str, k: int = 10) -> NoReturn:
        """Placeholder for the mandatory single-query answer command."""
        del query, k
        self._not_implemented("answer")

    def answer_dataset(
        self,
        student_search_results_path: str,
        save_directory: str = "data/output/search_results_and_answer",
    ) -> NoReturn:
        """Placeholder for the mandatory dataset answer command."""
        del student_search_results_path, save_directory
        self._not_implemented("answer_dataset")

    def evaluate(
        self,
        student_search_results_path: str,
        dataset_path: str,
    ) -> NoReturn:
        """Placeholder for the local recall evaluation command."""
        del student_search_results_path, dataset_path
        self._not_implemented("evaluate")


def main() -> None:
    """Run the Python Fire command-line application."""
    fire.Fire(RagCli)
