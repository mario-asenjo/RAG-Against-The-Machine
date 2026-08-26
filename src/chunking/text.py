"""Markdown/text chunking with exact half-open source spans."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Literal

from src.domain import SourceChunk, SourceDocument

DEFAULT_MAX_CHUNK_SIZE = 2000


def chunk_text_document(
    document: SourceDocument,
    max_chunk_size: int = DEFAULT_MAX_CHUNK_SIZE,
) -> list[SourceChunk]:
    """Split a text document into exact, bounded, half-open source chunks."""
    if max_chunk_size <= 0:
        raise ValueError("max_chunk_size must be positive")
    if document.text.strip() == "":
        return []

    chunks: list[SourceChunk] = []
    pending_start: int | None = None
    pending_end = 0

    for block_start, block_end in _iter_text_block_ranges(document.text):
        if pending_start is None:
            pending_start = block_start
            pending_end = block_start

        if block_end - block_start > max_chunk_size:
            if pending_end > pending_start:
                chunks.append(
                    _make_chunk(document, pending_start, pending_end, "text")
                )
            chunks.extend(
                split_source_range(
                    document,
                    block_start,
                    block_end,
                    max_chunk_size,
                    "text",
                )
            )
            pending_start = None
            pending_end = block_end
            continue

        would_exceed_limit = block_end - pending_start > max_chunk_size
        if pending_end > pending_start and would_exceed_limit:
            chunks.append(
                _make_chunk(document, pending_start, pending_end, "text")
            )
            pending_start = block_start

        pending_end = block_end

    if pending_start is not None and pending_end > pending_start:
        chunks.append(
            _make_chunk(document, pending_start, pending_end, "text")
        )

    return chunks


def _iter_text_block_ranges(text: str) -> Iterator[tuple[int, int]]:
    """Yield paragraph ranges, including following blank-line separators."""
    start = 0
    cursor = 0
    has_content = False

    for line in text.splitlines(keepends=True):
        line_end = cursor + len(line)
        is_blank = line.strip() == ""
        has_content = has_content or not is_blank
        if is_blank and has_content:
            yield start, line_end
            start = line_end
            has_content = False
        cursor = line_end

    if start < len(text) and has_content:
        yield start, len(text)


def split_source_range(
    document: SourceDocument,
    start: int,
    end: int,
    max_chunk_size: int,
    chunk_type: Literal["python", "text"],
) -> list[SourceChunk]:
    """Split one oversized range into fixed-size exact slices."""
    return [
        _make_chunk(
            document,
            cursor,
            min(cursor + max_chunk_size, end),
            chunk_type,
        )
        for cursor in range(start, end, max_chunk_size)
    ]


def _make_chunk(
    document: SourceDocument,
    start: int,
    end: int,
    chunk_type: Literal["python", "text"],
) -> SourceChunk:
    """Build a chunk from a half-open slice of the original document text."""
    return SourceChunk(
        file_path=document.file_path,
        first_character_index=start,
        last_character_index=end,
        chunk_type=chunk_type,
        text=document.text[start:end],
    )
