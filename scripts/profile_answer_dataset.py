"""Profile public answer_dataset generation phases without changing outputs."""

from __future__ import annotations

import argparse
import gc
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Sequence, cast

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.application.use_cases import answer_search_result  # noqa: E402
from src.domain import MinimalSource, StudentSearchResults  # noqa: E402
from src.infrastructure import (  # noqa: E402
    INDEX_FILENAME,
    QwenGenerator,
    load_source_texts_from_connection,
)


def _milliseconds(start: float, end: float) -> float:
    """Return elapsed milliseconds."""
    return round((end - start) * 1000, 3)


class ProfilingGenerator:
    """Wrap QwenGenerator and record timing at its public boundary."""

    def __init__(self, inner: QwenGenerator) -> None:
        self.inner = inner
        self.supported_context_ms = 0.0
        self.context_fitting_tokenization_ms = 0.0
        self.generation_ms = 0.0
        self.count_calls = 0
        self.prompt_tokens = 0
        self.generated_tokens = 0

    @property
    def supported_context_tokens(self) -> int:
        """Time supported-context lookup."""
        start = time.perf_counter()
        value = self.inner.supported_context_tokens
        self.supported_context_ms += _milliseconds(start, time.perf_counter())
        return value

    def count_prompt_tokens(self, question: str, context: str) -> int:
        """Time prompt tokenization used for context fitting."""
        start = time.perf_counter()
        tokens = self.inner.count_prompt_tokens(question, context)
        self.context_fitting_tokenization_ms += _milliseconds(
            start, time.perf_counter()
        )
        self.count_calls += 1
        self.prompt_tokens = max(self.prompt_tokens, tokens)
        return tokens

    def generate(
        self,
        question: str,
        context: str,
        max_new_tokens: int,
    ) -> str:
        """Time generation and estimate generated tokens from answer text."""
        start = time.perf_counter()
        answer = self.inner.generate(question, context, max_new_tokens)
        self.generation_ms += _milliseconds(start, time.perf_counter())
        tokenizer = self.inner._tokenizer
        if tokenizer is not None:
            self.generated_tokens = len(tokenizer(answer).input_ids)
        return answer


def _ignore_thread_override(_threads: int) -> None:
    """Keep the process thread setting chosen by the profiler."""


def _set_thread_policy(thread_setting: str) -> int:
    """Apply requested thread count and bypass adapter default."""
    import torch

    original = torch.set_num_threads
    if thread_setting == "default":
        torch.set_num_threads = cast(Any, _ignore_thread_override)
    else:
        threads = int(thread_setting)
        original(threads)
        torch.set_num_threads = cast(Any, _ignore_thread_override)
    return int(torch.get_num_threads())


def _load_subset(path: Path, limit: int) -> StudentSearchResults:
    """Return the first sourced public results from an existing search file."""
    data = StudentSearchResults.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    sourced = [item for item in data.search_results if item.retrieved_sources]
    return StudentSearchResults(search_results=sourced[:limit], k=data.k)


def profile(
    student_search_results_path: str,
    index_directory: str = "data/processed",
    model_cache_directory: str = "models/huggingface",
    output_json: str = "data/output/profiling/issue41/profile.json",
    limit: int = 10,
    thread_setting: str = "4",
    token_budget: int = 2048,
    max_new_tokens: int = 128,
) -> None:
    """Run one profiling pass and write JSON evidence."""
    effective_threads = _set_thread_policy(thread_setting)
    subset = _load_subset(Path(student_search_results_path), limit)
    index_path = Path(index_directory) / INDEX_FILENAME
    output_path = Path(output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    generator = ProfilingGenerator(
        QwenGenerator(
            cache_directory=Path(model_cache_directory),
            local_files_only=True,
            show_progress=False,
            progress_position=1,
            progress_leave=False,
        )
    )
    records: list[dict[str, Any]] = []
    total_start = time.perf_counter()
    with sqlite3.connect(index_path) as connection:
        for ordinal, search_result in enumerate(
            subset.search_results,
            start=1,
        ):
            generator.supported_context_ms = 0.0
            generator.context_fitting_tokenization_ms = 0.0
            generator.generation_ms = 0.0
            generator.count_calls = 0
            generator.prompt_tokens = 0
            generator.generated_tokens = 0
            hydration_ms = 0.0

            def load_sources(sources: Sequence[MinimalSource]) -> list[str]:
                nonlocal hydration_ms
                start = time.perf_counter()
                texts = load_source_texts_from_connection(connection, sources)
                hydration_ms += _milliseconds(start, time.perf_counter())
                return texts

            question_start = time.perf_counter()
            result = answer_search_result(
                search_result,
                load_sources,
                generator,
                token_budget=token_budget,
                max_new_tokens=max_new_tokens,
            )
            question_ms = _milliseconds(question_start, time.perf_counter())
            records.append(
                {
                    "ordinal": ordinal,
                    "question_id": search_result.question_id,
                    "question": search_result.question,
                    "retrieved_source_count": len(
                        search_result.retrieved_sources
                    ),
                    "included_source_count": len(result.included_sources),
                    "supported_context_ms": generator.supported_context_ms,
                    "source_hydration_ms": hydration_ms,
                    "context_fitting_tokenization_ms": (
                        generator.context_fitting_tokenization_ms
                    ),
                    "generation_ms": generator.generation_ms,
                    "total_question_ms": question_ms,
                    "prompt_tokens": generator.prompt_tokens,
                    "generated_tokens": generator.generated_tokens,
                    "answer_chars": len(result.answer.answer),
                }
            )
            output_path.write_text(
                json.dumps(
                    {
                        "thread_setting": thread_setting,
                        "effective_threads": effective_threads,
                        "limit": limit,
                        "records": records,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            gc.collect()

    total_ms = _milliseconds(total_start, time.perf_counter())
    generation_total_ms = sum(item["generation_ms"] for item in records)
    output_path.write_text(
        json.dumps(
            {
                "thread_setting": thread_setting,
                "effective_threads": effective_threads,
                "limit": limit,
                "total_ms": total_ms,
                "avg_question_ms": round(total_ms / max(len(records), 1), 3),
                "generation_total_ms": round(generation_total_ms, 3),
                "generation_share": round(generation_total_ms / total_ms, 4),
                "records": records,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(output_path.as_posix())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("student_search_results_path")
    parser.add_argument("--index-directory", default="data/processed")
    parser.add_argument(
        "--model-cache-directory",
        default="models/huggingface",
    )
    parser.add_argument(
        "--output-json",
        default="data/output/profiling/issue41/profile.json",
    )
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--thread-setting", default="4")
    parser.add_argument("--token-budget", type=int, default=2048)
    parser.add_argument("--max-new-tokens", type=int, default=128)
    args = parser.parse_args()
    profile(
        args.student_search_results_path,
        index_directory=args.index_directory,
        model_cache_directory=args.model_cache_directory,
        output_json=args.output_json,
        limit=args.limit,
        thread_setting=args.thread_setting,
        token_budget=args.token_budget,
        max_new_tokens=args.max_new_tokens,
    )
