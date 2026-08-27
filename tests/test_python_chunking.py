"""Tests for structure-aware Python chunking with exact source spans."""

from __future__ import annotations

import pytest

from src.chunking import chunk_python_document
from src.domain import SourceChunk, SourceDocument


def assert_exact_python_chunks(
    chunks: list[SourceChunk],
    original: str,
    max_chunk_size: int,
) -> None:
    """Assert chunks cover the exact original Python source once, in order."""
    assert "".join(chunk.text for chunk in chunks) == original
    assert all(chunk.chunk_type == "python" for chunk in chunks)
    previous_end = 0
    for chunk in chunks:
        assert chunk.first_character_index == previous_end
        assert chunk.last_character_index - previous_end <= max_chunk_size
        assert chunk.text == original[
            chunk.first_character_index:chunk.last_character_index
        ]
        previous_end = chunk.last_character_index


def test_python_chunker_prefers_decorated_functions_and_classes() -> None:
    """Top-level definitions should start distinct structural chunks."""
    text = (
        '"""Module docs."""\r\n'
        "import os\r\n"
        "\r\n"
        "# Helper context.\r\n"
        "@decorator\r\n"
        "def greet(name: str) -> str:\r\n"
        '    """Say hello."""\r\n'
        '    return f"Olá, {name}"\r\n'
        "\r\n"
        "class Runner:\r\n"
        "    def run(self) -> str:\r\n"
        '        return greet("world")\r\n'
    )
    document = SourceDocument(
        file_path="data/raw/vllm-0.10.1/vllm/example.py",
        text=text,
    )

    chunks = chunk_python_document(document)

    assert len(chunks) == 3
    assert chunks[0].text.startswith('"""Module docs."""')
    assert "# Helper context." in chunks[0].text
    assert chunks[1].text.startswith("@decorator\r\ndef greet")
    assert chunks[2].text.startswith("class Runner:")
    assert_exact_python_chunks(chunks, text, 2000)


def test_python_chunker_handles_module_code_without_definitions() -> None:
    """A module without definitions remains one exact Python chunk."""
    text = "import os\nVALUE = 'café'\n"
    document = SourceDocument(
        file_path="data/raw/vllm-0.10.1/vllm/config.py",
        text=text,
    )

    chunks = chunk_python_document(document)

    assert [chunk.text for chunk in chunks] == [text]
    assert_exact_python_chunks(chunks, text, 2000)


def test_python_chunker_splits_oversized_definition_without_loss() -> None:
    """Oversized Python structures should reuse the exact bounded fallback."""
    text = "def huge():\n" + "    value = 1\n" * 5
    document = SourceDocument(
        file_path="data/raw/vllm-0.10.1/vllm/huge.py",
        text=text,
    )

    chunks = chunk_python_document(document, max_chunk_size=20)

    assert len(chunks) > 1
    assert_exact_python_chunks(chunks, text, 20)


def test_python_chunker_falls_back_for_invalid_syntax() -> None:
    """Invalid Python should be chunked safely instead of aborting indexing."""
    text = "def broken(:\n    return 'still source'\n"
    document = SourceDocument(
        file_path="data/raw/vllm-0.10.1/vllm/broken.py",
        text=text,
    )

    chunks = chunk_python_document(document, max_chunk_size=12)

    assert_exact_python_chunks(chunks, text, 12)


@pytest.mark.parametrize("text", ["", " \r\n\t"])
def test_python_chunker_returns_no_chunks_for_empty_or_whitespace(
    text: str,
) -> None:
    """Empty Python files have no retrievable content chunks."""
    document = SourceDocument(
        file_path="data/raw/vllm-0.10.1/vllm/empty.py",
        text=text,
    )

    assert chunk_python_document(document) == []


def test_python_chunker_rejects_non_positive_max_size() -> None:
    """A non-positive max size cannot produce bounded Python chunks."""
    document = SourceDocument(
        file_path="data/raw/vllm-0.10.1/vllm/example.py",
        text="pass\n",
    )

    with pytest.raises(ValueError, match="max_chunk_size must be positive"):
        chunk_python_document(document, max_chunk_size=0)
