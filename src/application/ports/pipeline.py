"""Application-facing operations implemented by the local runtime."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from src.application.models import (
    AnswerCommand,
    IndexCommand,
    IndexOperationResult,
    RetrievalCommand,
)
from src.application.ports.generation import TextGenerator
from src.domain import MinimalSource


class PipelineOperations(Protocol):
    """Provide concrete I/O and model operations to shared use cases."""

    def index(
        self,
        command: IndexCommand,
        show_progress: bool = False,
    ) -> IndexOperationResult:
        """Build or update canonical and optional semantic indexes."""
        ...

    def retrieve(
        self,
        command: RetrievalCommand,
        queries: list[str],
        batch: bool = False,
        show_progress: bool = False,
    ) -> list[list[MinimalSource]]:
        """Retrieve ordered exact sources for each query."""
        ...

    def load_source_texts(
        self,
        index_directory: str,
        sources: Sequence[MinimalSource],
    ) -> list[str]:
        """Hydrate exact canonical source identities in order."""
        ...

    def make_generator(
        self,
        command: AnswerCommand,
        show_progress: bool = False,
    ) -> TextGenerator:
        """Construct the configured lazy text generator."""
        ...
