"""Tests for deterministic corpus discovery and exact text loading."""

from pathlib import Path

import pytest

from src.infrastructure.corpus import load_corpus


def test_load_corpus_preserves_paths_order_and_raw_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Accepted files keep deterministic paths and exact original text."""
    monkeypatch.chdir(tmp_path)
    corpus_root = Path("data/raw/vllm-0.10.1")

    markdown = corpus_root / "docs" / "guide.md"
    text = corpus_root / "docs" / "notes.txt"
    python = corpus_root / "vllm" / "engine.py"
    ignored = corpus_root / "metadata.json"

    markdown.parent.mkdir(parents=True)
    python.parent.mkdir(parents=True)

    markdown.write_bytes("Título\r\n\r\nContenido\r\n".encode("utf-8"))
    text.write_bytes(b"plain text\r\n")
    python.write_bytes(b"def run():\r\n    return True\r\n")
    ignored.write_text("{}", encoding="utf-8")

    documents = load_corpus(corpus_root)

    assert [document.file_path for document in documents] == [
        "data/raw/vllm-0.10.1/docs/guide.md",
        "data/raw/vllm-0.10.1/docs/notes.txt",
        "data/raw/vllm-0.10.1/vllm/engine.py",
    ]
    assert documents[0].text == "Título\r\n\r\nContenido\r\n"
    assert documents[1].text == "plain text\r\n"
    assert documents[2].text == "def run():\r\n    return True\r\n"


def test_load_corpus_rejects_missing_root(tmp_path: Path) -> None:
    """A missing corpus root should fail with a clear filesystem error."""
    missing_root = tmp_path / "missing"

    with pytest.raises(FileNotFoundError, match="Corpus root not found"):
        load_corpus(missing_root)


def test_load_corpus_rejects_invalid_utf8(tmp_path: Path) -> None:
    """An invalid accepted file should fail rather than be silently skipped."""
    corpus_root = tmp_path / "corpus"
    corpus_root.mkdir()
    (corpus_root / "invalid.py").write_bytes(b"\xff")

    with pytest.raises(UnicodeDecodeError):
        load_corpus(corpus_root)
