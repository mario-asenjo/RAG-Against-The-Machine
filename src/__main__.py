"""Python Fire entry point for the incremental project scaffold."""

from typing import NoReturn

import fire


class RagCli:
    """Expose project commands as they are implemented issue by issue."""

    @staticmethod
    def status() -> str:
        """Return the current scaffold status."""
        return (
            "Harness ready. Mandatory RAG commands are intentionally not "
            "implemented yet; follow the active GitHub issue."
        )

    @staticmethod
    def _not_implemented(command: str) -> NoReturn:
        """Fail gracefully for a command whose implementation is pending."""
        raise fire.core.FireError(
            f"'{command}' is not implemented yet. "
        )

    def index(self, max_chunk_size: int = 2000) -> NoReturn:
        """Placeholder for the mandatory index command."""
        del max_chunk_size
        self._not_implemented("index")

    def search(self, query: str, k: int = 10) -> NoReturn:
        """Placeholder for the mandatory single-query search command."""
        del query, k
        self._not_implemented("search")

    def search_dataset(
        self,
        dataset_path: str,
        k: int = 10,
        save_directory: str = "data/output/search_results",
    ) -> NoReturn:
        """Placeholder for the mandatory dataset search command."""
        del dataset_path, k, save_directory
        self._not_implemented("search_dataset")

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


if __name__ == "__main__":
    main()
