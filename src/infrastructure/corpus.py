"""Deterministic discovery and exact loading of corpus text files."""

from pathlib import Path

from tqdm import tqdm

from src.domain import SourceDocument


SUPPORTED_SUFFIXES = {".md", ".py", ".txt"}


def load_corpus(
    corpus_path: Path,
    show_progress: bool = False,
) -> list[SourceDocument]:
    """Load supported UTF-8 files exactly, failing fast on unreadable input."""
    if not corpus_path.is_dir():
        raise FileNotFoundError(f"Corpus root not found: {corpus_path}")

    discovered_paths = tqdm(
        corpus_path.rglob("*"),
        desc="Discovering corpus",
        unit=" paths found",
        disable=not show_progress,
    )
    paths = sorted(
        (
            path
            for path in discovered_paths
            if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
        ),
        key=lambda item: item.as_posix(),
    )
    documents: list[SourceDocument] = []
    for path in tqdm(
        paths,
        desc="Loading corpus",
        unit="file",
        disable=not show_progress,
    ):
        with path.open("r", encoding="utf-8", newline="") as source_file:
            documents.append(
                SourceDocument(
                    file_path=path.as_posix(),
                    text=source_file.read(),
                )
            )
    return documents
