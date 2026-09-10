"""Ground one answer in exact retrieved source text."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from src.application.ports import TextGenerator
from src.domain import MinimalAnswer, MinimalSearchResults, MinimalSource

ABSTENTION_ANSWER = "I cannot answer from the retrieved sources."
SourceTextLoader = Callable[[Sequence[MinimalSource]], list[str]]


@dataclass(frozen=True)
class AnswerGeneration:
    """Generated contract plus the retrieved sources included in its prompt."""

    answer: MinimalAnswer
    included_sources: tuple[MinimalSource, ...]


def answer_search_result(
    search_result: MinimalSearchResults,
    load_source_texts: SourceTextLoader,
    generator: TextGenerator,
    token_budget: int = 2048,
    max_new_tokens: int = 128,
) -> AnswerGeneration:
    """Hydrate ranked sources, fit a complete-prefix context, and answer."""
    _validate_budget(token_budget, max_new_tokens)
    if not search_result.retrieved_sources:
        return AnswerGeneration(
            answer=MinimalAnswer(
                **search_result.model_dump(),
                answer=ABSTENTION_ANSWER,
            ),
            included_sources=(),
        )

    if token_budget > generator.supported_context_tokens:
        raise ValueError(
            "token_budget exceeds the generator's supported context"
        )
    if (
        generator.count_prompt_tokens(search_result.question, "")
        + max_new_tokens
        > token_budget
    ):
        raise ValueError(
            "question and instructions exceed token_budget with the "
            "reserved answer"
        )

    texts = load_source_texts(search_result.retrieved_sources)
    if len(texts) != len(search_result.retrieved_sources):
        raise RuntimeError("source loader returned an incomplete result")

    included_sources: list[MinimalSource] = []
    fragments: list[str] = []
    for rank, (source, text) in enumerate(
        zip(search_result.retrieved_sources, texts), start=1
    ):
        fragment = _format_fragment(rank, source, text)
        candidate = "\n\n".join([*fragments, fragment])
        prompt_tokens = generator.count_prompt_tokens(
            search_result.question, candidate
        )
        if prompt_tokens + max_new_tokens > token_budget:
            break
        fragments.append(fragment)
        included_sources.append(source)

    if not fragments:
        raise ValueError("No complete source fits within token_budget")

    context = "\n\n".join(fragments)
    answer_text = generator.generate(
        search_result.question,
        context,
        max_new_tokens,
    ).strip()
    if not answer_text:
        raise RuntimeError("generator returned an empty answer")

    return AnswerGeneration(
        answer=MinimalAnswer(
            **search_result.model_dump(),
            answer=answer_text,
        ),
        included_sources=tuple(included_sources),
    )


def _validate_budget(token_budget: int, max_new_tokens: int) -> None:
    """Reject invalid operational budgets without touching model assets."""
    if token_budget <= 0:
        raise ValueError("token_budget must be positive")
    if max_new_tokens <= 0:
        raise ValueError("max_new_tokens must be positive")
    if max_new_tokens >= token_budget:
        raise ValueError("max_new_tokens must be smaller than token_budget")


def _format_fragment(
    rank: int,
    source: MinimalSource,
    text: str,
) -> str:
    """Label an exact source without altering its persisted text."""
    return (
        f"[Source {rank}: {source.file_path} "
        f"[{source.first_character_index}:{source.last_character_index}]]\n"
        f"{text}"
    )
