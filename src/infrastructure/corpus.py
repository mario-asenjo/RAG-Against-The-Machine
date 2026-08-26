"""Deterministic discovery and exact loading of corpus text files."""

from pathlib import Path

from src.domain import SourceDocument


SUPPORTED_SUFFIXES = {".md", ".py", ".txt"}


def load_corpus(corpus_path: Path) -> list[SourceDocument]:
    """Load supported UTF-8 files exactly, failing fast on unreadable input."""
    if not corpus_path.is_dir():
        raise FileNotFoundError(f"Corpus root not found: {corpus_path}")

    documents: list[SourceDocument] = []
    paths = sorted(corpus_path.rglob("*"), key=lambda item: item.as_posix())
    for path in paths:
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        with path.open("r", encoding="utf-8", newline="") as source_file:
            documents.append(
                SourceDocument(
                    file_path=path.as_posix(),
                    text=source_file.read(),
                )
            )
    return documents
