"""Fuse lexical and semantic source rankings without score calibration."""

from __future__ import annotations

from collections.abc import Sequence

from src.domain import MinimalSource

RRF_RANK_CONSTANT = 60


def fuse_ranked_sources(
    lexical: Sequence[MinimalSource],
    semantic: Sequence[MinimalSource],
    k: int,
) -> list[MinimalSource]:
    """Return deterministic equal-weight reciprocal-rank fusion results."""
    if k < 0:
        raise ValueError("k must be non-negative")
    if k == 0:
        return []

    scores: dict[tuple[str, int, int], float] = {}
    sources: dict[tuple[str, int, int], MinimalSource] = {}
    for ranking in (lexical, semantic):
        seen: set[tuple[str, int, int]] = set()
        for rank, source in enumerate(ranking, start=1):
            identity = _identity(source)
            if identity in seen:
                continue
            seen.add(identity)
            scores[identity] = scores.get(identity, 0.0) + 1.0 / (
                RRF_RANK_CONSTANT + rank
            )
            sources[identity] = source

    ordered = sorted(scores, key=lambda item: (-scores[item], item))[:k]
    return [sources[identity] for identity in ordered]


def _identity(source: MinimalSource) -> tuple[str, int, int]:
    """Return the evaluator-visible exact source identity."""
    return (
        source.file_path,
        source.first_character_index,
        source.last_character_index,
    )
