"""Structure-aware Python chunking with exact half-open source spans."""

from __future__ import annotations

import ast

from src.chunking.text import DEFAULT_MAX_CHUNK_SIZE, split_source_range
from src.domain import SourceChunk, SourceDocument

_STRUCTURAL_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def chunk_python_document(
    document: SourceDocument,
    max_chunk_size: int = DEFAULT_MAX_CHUNK_SIZE,
) -> list[SourceChunk]:
    """Split Python at top-level definitions with a safe bounded fallback."""
    if max_chunk_size <= 0:
        raise ValueError("max_chunk_size must be positive")
    if document.text.strip() == "":
        return []

    try:
        tree = ast.parse(document.text)
    except (SyntaxError, ValueError):
        return _chunk_range(document, 0, len(document.text), max_chunk_size)

    structural_starts = _structural_starts(tree, document.text)
    boundaries = _chunk_boundaries(document.text, structural_starts)
    chunks: list[SourceChunk] = []
    for start, end in zip(boundaries, boundaries[1:]):
        chunks.extend(_chunk_range(document, start, end, max_chunk_size))
    return chunks


def _structural_starts(tree: ast.Module, text: str) -> list[int]:
    """Return exact line-start offsets for top-level classes and functions."""
    line_starts = _line_starts(text)
    starts: list[int] = []
    for node in tree.body:
        if not isinstance(node, _STRUCTURAL_NODES):
            continue
        lines = [node.lineno]
        lines.extend(decorator.lineno for decorator in node.decorator_list)
        starts.append(line_starts[min(lines) - 1])
    return starts


def _line_starts(text: str) -> list[int]:
    """Map one-based AST line numbers to exact character offsets."""
    starts = [0]
    cursor = 0
    for line in text.splitlines(keepends=True):
        cursor += len(line)
        starts.append(cursor)
    return starts


def _chunk_boundaries(text: str, structural_starts: list[int]) -> list[int]:
    """Keep module preamble and each top-level definition deterministic."""
    boundaries = [0]
    for start in structural_starts:
        if start == 0:
            continue
        if len(boundaries) == 1 and text[:start].strip() == "":
            continue
        boundaries.append(start)
    boundaries.append(len(text))
    return boundaries


def _chunk_range(
    document: SourceDocument,
    start: int,
    end: int,
    max_chunk_size: int,
) -> list[SourceChunk]:
    """Reuse the exact bounded fallback while retaining Python metadata."""
    return split_source_range(
        document,
        start,
        end,
        max_chunk_size,
        "python",
    )
