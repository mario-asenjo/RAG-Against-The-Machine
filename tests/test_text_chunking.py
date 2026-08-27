"""Tests for Markdown/text chunking with exact source spans."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.chunking import chunk_text_document
from src.domain import SourceChunk, SourceDocument


def assert_chunks_rebuild_text(
    chunks: list[SourceChunk],
    original: str,
) -> None:
    """Assert chunk spans are half-open exact slices of the original text."""
    rebuilt = ""
    previous_end = 0
    for chunk in chunks:
        assert chunk.first_character_index == previous_end
        source_slice = original[
            chunk.first_character_index:chunk.last_character_index
        ]
        assert chunk.text == source_slice
        rebuilt += chunk.text
        previous_end = chunk.last_character_index
    assert rebuilt == original


def test_chunk_text_document_prefers_blocks_and_crlf_unicode() -> None:
    """Markdown/text chunks should split on blank-line blocks when they fit."""
    text = "# Title\r\n\r\nIntro café.\r\n\r\n## Usage\r\n\r\nRun it.\r\n"
    document = SourceDocument(
        file_path="data/raw/vllm-0.10.1/docs/index.md",
        text=text,
    )

    chunks = chunk_text_document(document, max_chunk_size=26)

    assert [chunk.text for chunk in chunks] == [
        "# Title\r\n\r\nIntro café.\r\n\r\n",
        "## Usage\r\n\r\nRun it.\r\n",
    ]
    assert [chunk.file_path for chunk in chunks] == [document.file_path] * 2
    assert all(chunk.chunk_type == "text" for chunk in chunks)
    assert_chunks_rebuild_text(chunks, text)
    assert all(
        chunk.last_character_index - chunk.first_character_index <= 26
        for chunk in chunks
    )


@pytest.mark.parametrize("text", ["", "   \n\t\r\n"])
def test_chunk_text_document_returns_no_chunks_for_empty_or_whitespace(
    text: str,
) -> None:
    """Empty or whitespace-only text has no retrievable content chunks."""
    document = SourceDocument(
        file_path="data/raw/vllm-0.10.1/README.md",
        text=text,
    )

    assert chunk_text_document(document) == []


def test_chunk_text_document_splits_oversized_blocks_without_loss() -> None:
    """Indivisible blocks over the limit should be split into exact slices."""
    text = "A" * 11 + "\n\n" + "B" * 3
    document = SourceDocument(
        file_path="data/raw/vllm-0.10.1/docs/long.txt",
        text=text,
    )

    chunks = chunk_text_document(document, max_chunk_size=5)

    assert [chunk.text for chunk in chunks] == [
        "AAAAA",
        "AAAAA",
        "A\n\n",
        "BBB",
    ]
    assert_chunks_rebuild_text(chunks, text)
    assert all(
        chunk.last_character_index - chunk.first_character_index <= 5
        for chunk in chunks
    )


def test_chunk_text_document_defaults_to_2000_character_limit() -> None:
    """The subject default max chunk size is 2000 characters."""
    document = SourceDocument(
        file_path="data/raw/vllm-0.10.1/docs/long.md",
        text="x" * 2001,
    )

    chunks = chunk_text_document(document)

    assert [len(chunk.text) for chunk in chunks] == [2000, 1]
    assert_chunks_rebuild_text(chunks, document.text)


def test_chunk_text_document_rejects_non_positive_max_size() -> None:
    """A non-positive max size cannot produce bounded chunks."""
    document = SourceDocument(
        file_path="data/raw/vllm-0.10.1/README.md",
        text="content",
    )

    with pytest.raises(ValueError, match="max_chunk_size must be positive"):
        chunk_text_document(document, max_chunk_size=0)


def test_source_chunk_rejects_text_that_does_not_match_span_width() -> None:
    """Chunk text length must match the half-open source span width."""
    with pytest.raises(ValidationError):
        SourceChunk(
            file_path="data/raw/vllm-0.10.1/README.md",
            first_character_index=0,
            last_character_index=5,
            chunk_type="text",
            text="tiny",
        )
