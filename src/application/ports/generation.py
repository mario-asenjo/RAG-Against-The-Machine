"""Minimum generation seam for grounded answer use cases."""

from __future__ import annotations

from typing import Protocol


class TextGenerator(Protocol):
    """Count the real prompt and generate answer text from grounded context."""

    @property
    def supported_context_tokens(self) -> int:
        """Return the maximum supported complete sequence length."""
        ...

    def count_prompt_tokens(self, question: str, context: str) -> int:
        """Count the complete templated prompt, including special tokens."""
        ...

    def generate(
        self,
        question: str,
        context: str,
        max_new_tokens: int,
    ) -> str:
        """Generate answer text only from a question and grounded context."""
        ...
