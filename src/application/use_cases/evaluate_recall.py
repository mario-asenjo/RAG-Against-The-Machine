"""Pure macro Recall@k evaluation for retrieved source spans."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TypeVar

from src.domain import (
    AnsweredQuestion,
    MinimalSource,
    RagDataset,
    StudentSearchResults,
    UnansweredQuestion,
)

DEFAULT_CUTOFFS = (1, 3, 5, 10)
QuestionT = TypeVar("QuestionT", bound=UnansweredQuestion)


@dataclass(frozen=True)
class RecallEvaluation:
    """Aggregate diagnostics and macro Recall@k values."""

    total_questions: int
    questions_evaluated: int
    questions_with_student_sources: int
    recall_at: dict[int, float]


def source_iou(candidate: MinimalSource, expected: MinimalSource) -> float:
    """Return half-open range intersection over union."""
    intersection = max(
        0,
        min(candidate.last_character_index, expected.last_character_index)
        - max(candidate.first_character_index, expected.first_character_index),
    )
    candidate_length = (
        candidate.last_character_index - candidate.first_character_index
    )
    expected_length = (
        expected.last_character_index - expected.first_character_index
    )
    union = candidate_length + expected_length - intersection
    return intersection / union if union > 0 else 0.0


def source_matches(
    candidate: MinimalSource,
    expected: MinimalSource,
    min_iou: float = 0.05,
) -> bool:
    """Match exact paths whose range IoU strictly exceeds the floor."""
    return (
        candidate.file_path == expected.file_path
        and source_iou(candidate, expected) > min_iou
    )


def question_recall(
    retrieved: Sequence[MinimalSource],
    expected_sources: Sequence[MinimalSource],
    k: int,
    min_iou: float = 0.05,
) -> float:
    """Return the proportion of expected sources found within top-k results."""
    if k < 0:
        raise ValueError("k must be non-negative")
    if not expected_sources:
        raise ValueError("expected_sources must not be empty")
    found_count = sum(
        any(
            source_matches(candidate, expected_source, min_iou)
            for candidate in retrieved[:k]
        )
        for expected_source in expected_sources
    )
    return found_count / len(expected_sources)


def _index_by_question_id(
    questions: Sequence[QuestionT],
    label: str,
) -> dict[str, QuestionT]:
    """Index questions while rejecting ambiguous duplicate identifiers."""
    indexed: dict[str, QuestionT] = {}
    for question in questions:
        if question.question_id in indexed:
            raise ValueError(
                f"Duplicate question_id in {label}: {question.question_id}"
            )
        indexed[question.question_id] = question
    return indexed


def evaluate_search_results(
    student: StudentSearchResults,
    dataset: RagDataset,
    cutoffs: Sequence[int] = DEFAULT_CUTOFFS,
    min_iou: float = 0.05,
    max_context_length: int = 2000,
) -> RecallEvaluation:
    """Macro-average per-question source recall at each requested cutoff."""
    if max_context_length <= 0:
        raise ValueError("max_context_length must be positive")
    if not 0 <= min_iou <= 1:
        raise ValueError("min_iou must be between 0 and 1")
    if not cutoffs or any(k < 0 for k in cutoffs):
        raise ValueError("cutoffs must contain non-negative values")

    ground_truth = _index_by_question_id(dataset.rag_questions, "ground truth")
    student_results = _index_by_question_id(
        student.search_results,
        "student results",
    )
    unknown_ids = [
        question_id
        for question_id in student_results
        if question_id not in ground_truth
    ]
    if unknown_ids:
        raise ValueError(f"Unknown student question_id: {unknown_ids[0]}")

    for result in student.search_results:
        for candidate in result.retrieved_sources:
            if (
                candidate.last_character_index
                - candidate.first_character_index
                > max_context_length
            ):
                raise ValueError(
                    "Student source exceeds max_context_length: "
                    f"{candidate.file_path}"
                )

    evaluable = [
        question
        for question in dataset.rag_questions
        if isinstance(question, AnsweredQuestion) and question.sources
    ]
    if not evaluable:
        raise ValueError("Dataset has no questions with ground-truth sources")

    recall_at = {
        k: sum(
            question_recall(
                (
                    student_results[question.question_id].retrieved_sources
                    if question.question_id in student_results
                    else ()
                ),
                question.sources,
                k,
                min_iou,
            )
            for question in evaluable
        )
        / len(evaluable)
        for k in cutoffs
    }
    questions_with_student_sources = sum(
        bool(
            question.question_id in student_results
            and student_results[question.question_id].retrieved_sources
        )
        for question in dataset.rag_questions
    )
    return RecallEvaluation(
        total_questions=len(dataset.rag_questions),
        questions_evaluated=len(evaluable),
        questions_with_student_sources=questions_with_student_sources,
        recall_at=recall_at,
    )
