"""Tests for student-owned macro Recall@k evaluation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from src.application.use_cases.evaluate_recall import (
    evaluate_search_results,
    question_recall,
    source_iou,
    source_matches,
)
from src.domain import (
    AnsweredQuestion,
    MinimalSearchResults,
    MinimalSource,
    RagDataset,
    StudentSearchResults,
    UnansweredQuestion,
)

ROOT = Path(__file__).resolve().parents[1]


def source(
    file_path: str = "data/raw/vllm-0.10.1/file.py",
    first: int = 0,
    last: int = 10,
) -> MinimalSource:
    """Build a compact source fixture."""
    return MinimalSource(
        file_path=file_path,
        first_character_index=first,
        last_character_index=last,
    )


def answered(
    question_id: str,
    sources: list[MinimalSource],
) -> AnsweredQuestion:
    """Build an answered ground-truth question."""
    return AnsweredQuestion(
        question_id=question_id,
        question=f"Question {question_id}",
        sources=sources,
        answer="Answer",
    )


def result(
    question_id: str,
    sources: list[MinimalSource],
) -> MinimalSearchResults:
    """Build one student result."""
    return MinimalSearchResults(
        question_id=question_id,
        question=f"Question {question_id}",
        retrieved_sources=sources,
    )


def test_source_iou_uses_half_open_ranges() -> None:
    """Intersection and union should use the project's half-open spans."""
    overlap = source_iou(
        source(first=10, last=20),
        source(first=15, last=25),
    )

    assert overlap == pytest.approx(5 / 15)
    empty = source_iou(
        source(first=10, last=10),
        source(first=10, last=10),
    )
    assert empty == 0


def test_source_match_requires_exact_path_and_overlap() -> None:
    """Numeric overlap never compensates for a different file path."""
    expected = source(first=0, last=10)

    assert not source_matches(source("other.py", 0, 10), expected)
    assert not source_matches(source(first=10, last=20), expected)


def test_source_match_uses_strict_iou_threshold() -> None:
    """IoU equal to 0.05 fails while a larger value passes."""
    expected = source(first=0, last=20)

    assert not source_matches(source(first=19, last=20), expected)
    assert source_matches(source(first=18, last=20), expected)


def test_question_recall_respects_rank_cutoff() -> None:
    """A source at rank two is absent at R@1 and present at R@3."""
    expected = [source()]
    retrieved = [source("wrong.py"), source()]

    assert question_recall(retrieved, expected, k=1) == 0.0
    assert question_recall(retrieved, expected, k=3) == 1.0


def test_question_recall_counts_each_ground_truth_source_once() -> None:
    """Finding one of two expected sources yields 0.5 despite duplicates."""
    first = source("first.py", 0, 10)
    second = source("second.py", 20, 30)

    assert question_recall([first, first], [first, second], k=10) == 0.5


def test_evaluation_is_macro_recall_not_micro_or_hit_rate() -> None:
    """Per-question recall must be macro-averaged."""
    first = source("first.py", 0, 10)
    second = source("second.py", 20, 30)
    dataset = RagDataset(
        rag_questions=[
            answered("q1", [first, second]),
            answered("q2", [source("third.py", 40, 50)]),
        ]
    )
    student = StudentSearchResults(
        search_results=[result("q1", [first]), result("q2", [])],
        k=10,
    )

    evaluation = evaluate_search_results(student, dataset, cutoffs=(10,))

    assert evaluation.recall_at == {10: 0.25}
    assert evaluation.questions_evaluated == 2


def test_missing_student_result_is_empty_retrieval() -> None:
    """Missing output for a known question contributes zero recall."""
    dataset = RagDataset(rag_questions=[answered("q1", [source()])])
    student = StudentSearchResults(search_results=[], k=10)

    evaluation = evaluate_search_results(student, dataset, cutoffs=(5,))

    assert evaluation.recall_at == {5: 0.0}
    assert evaluation.questions_with_student_sources == 0


@pytest.mark.parametrize("side", ["student", "ground_truth"])
def test_evaluation_rejects_duplicate_question_ids(side: str) -> None:
    """Duplicate IDs make question matching ambiguous on either side."""
    questions: list[UnansweredQuestion | AnsweredQuestion] = [
        answered("q1", [source()])
    ]
    results = [result("q1", [source()])]
    if side == "student":
        results *= 2
    else:
        questions *= 2

    with pytest.raises(ValueError, match="Duplicate question_id"):
        evaluate_search_results(
            StudentSearchResults(search_results=results, k=10),
            RagDataset(rag_questions=questions),
        )


def test_evaluation_rejects_unknown_student_question_id() -> None:
    """Student results may not silently target absent ground truth IDs."""
    with pytest.raises(ValueError, match="Unknown student question_id"):
        evaluate_search_results(
            StudentSearchResults(
                search_results=[result("unknown", [source()])],
                k=10,
            ),
            RagDataset(rag_questions=[answered("q1", [source()])]),
        )


def test_evaluation_excludes_questions_without_ground_truth_sources() -> None:
    """Questions without sources stay outside the macro denominator."""
    dataset = RagDataset(
        rag_questions=[
            answered("q1", [source()]),
            answered("q2", []),
        ]
    )
    student = StudentSearchResults(
        search_results=[result("q1", [source()]), result("q2", [])],
        k=10,
    )

    evaluation = evaluate_search_results(student, dataset, cutoffs=(5,))

    assert evaluation.total_questions == 2
    assert evaluation.questions_evaluated == 1
    assert evaluation.recall_at == {5: 1.0}


def test_evaluation_rejects_empty_ground_truth_and_oversized_source() -> None:
    """Evaluation needs a denominator and evaluator-valid student spans."""
    with pytest.raises(ValueError, match="ground-truth sources"):
        evaluate_search_results(
            StudentSearchResults(search_results=[], k=10),
            RagDataset(rag_questions=[]),
        )

    with pytest.raises(ValueError, match="max_context_length"):
        evaluate_search_results(
            StudentSearchResults(
                search_results=[result("q1", [source(last=2001)])],
                k=10,
            ),
            RagDataset(rag_questions=[answered("q1", [source()])]),
        )


def run_evaluate(
    student_path: Path,
    dataset_path: Path,
) -> subprocess.CompletedProcess[str]:
    """Run evaluate through the Fire CLI."""
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "src",
            "evaluate",
            f"--student_search_results_path={student_path}",
            f"--dataset_path={dataset_path}",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_evaluate_cli_smoke_reports_macro_recall(tmp_path: Path) -> None:
    """CLI should load subject models and print stable Recall@k metrics."""
    expected = source()
    dataset_path = tmp_path / "answered.json"
    student_path = tmp_path / "student.json"
    dataset_path.write_text(
        RagDataset(
            rag_questions=[
                answered("q1", [expected, source("second.py")]),
            ]
        ).model_dump_json(),
        encoding="utf-8",
    )
    student_path.write_text(
        StudentSearchResults(
            search_results=[result("q1", [expected])],
            k=10,
        ).model_dump_json(),
        encoding="utf-8",
    )

    completed = run_evaluate(student_path, dataset_path)

    assert completed.returncode == 0, completed.stderr
    assert "Questions evaluated: 1" in completed.stdout
    assert "Recall@5: 0.500" in completed.stdout
    assert "recall@5" in completed.stdout


@pytest.mark.parametrize(
    ("student_content", "dataset_content", "student_is_invalid"),
    [
        (None, "{}", True),
        ("not json", "{}", True),
        ("{}", "{}", True),
        (
            '{"search_results": [], "k": 10}',
            '{"rag_questions": [{}]}',
            False,
        ),
    ],
)
def test_evaluate_cli_handles_invalid_input_without_traceback(
    tmp_path: Path,
    student_content: str | None,
    dataset_content: str,
    student_is_invalid: bool,
) -> None:
    """Missing, malformed, and schema-invalid input become concise errors."""
    student_path = tmp_path / "student.json"
    dataset_path = tmp_path / "dataset.json"
    if student_content is not None:
        student_path.write_text(student_content, encoding="utf-8")
    dataset_path.write_text(dataset_content, encoding="utf-8")

    completed = run_evaluate(student_path, dataset_path)

    assert completed.returncode != 0
    assert "Traceback" not in completed.stderr
    assert ("Student data is valid: False" in completed.stderr) is (
        student_is_invalid
    )


def test_evaluate_cli_marks_evaluation_errors_as_invalid_student_data(
    tmp_path: Path,
) -> None:
    """Semantic student-result errors should report invalid student data."""
    dataset_path = tmp_path / "answered.json"
    student_path = tmp_path / "student.json"
    dataset_path.write_text(
        RagDataset(
            rag_questions=[answered("q1", [source()])]
        ).model_dump_json(),
        encoding="utf-8",
    )
    student_path.write_text(
        StudentSearchResults(
            search_results=[result("unknown", [source()])],
            k=10,
        ).model_dump_json(),
        encoding="utf-8",
    )

    completed = run_evaluate(student_path, dataset_path)

    assert completed.returncode != 0
    assert "Student data is valid: False" in completed.stderr
    assert "Traceback" not in completed.stderr
