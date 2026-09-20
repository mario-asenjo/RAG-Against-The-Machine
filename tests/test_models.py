"""Contract tests for evaluator-facing Pydantic models."""

from __future__ import annotations

import json
import uuid

import pytest
from pydantic import ValidationError

from src.domain import (
    AnsweredQuestion,
    IndexedFile,
    LexicalIndexBuild,
    LexicalIndexMetadata,
    MinimalAnswer,
    MinimalSearchResults,
    MinimalSource,
    RagDataset,
    SourceChunk,
    StudentSearchResults,
    StudentSearchResultsAndAnswer,
    UnansweredQuestion,
)


def test_minimal_source_serializes_exact_field_names() -> None:
    """Source spans should preserve the evaluator-facing JSON shape."""
    source = MinimalSource(
        file_path="data/raw/vllm-0.10.1/vllm/entrypoints/llm.py",
        first_character_index=10,
        last_character_index=42,
    )

    assert source.model_dump() == {
        "file_path": "data/raw/vllm-0.10.1/vllm/entrypoints/llm.py",
        "first_character_index": 10,
        "last_character_index": 42,
    }


@pytest.mark.parametrize(
    ("first", "last"),
    [(-1, 10), (10, -1), (42, 10)],
)
def test_minimal_source_rejects_invalid_ranges(first: int, last: int) -> None:
    """Negative or inverted source ranges are never valid output."""
    with pytest.raises(ValidationError):
        MinimalSource(
            file_path="data/raw/vllm-0.10.1/README.md",
            first_character_index=first,
            last_character_index=last,
        )


def test_required_fields_fail_predictably() -> None:
    """Missing evaluator-required fields should raise validation errors."""
    with pytest.raises(ValidationError):
        MinimalSource.model_validate({})
    with pytest.raises(ValidationError):
        UnansweredQuestion.model_validate({})


def test_unanswered_question_generates_subject_default_id() -> None:
    """A standalone subject question should receive a UUID string."""
    question = UnansweredQuestion(question="What is vLLM?")

    assert str(uuid.UUID(question.question_id)) == question.question_id


def test_lexical_index_build_rejects_stale_chunk_count() -> None:
    """Persisted metadata cannot disagree with its Pydantic chunk payload."""
    metadata = LexicalIndexMetadata(
        corpus_path="data/raw/vllm-0.10.1",
        max_chunk_size=2000,
        document_count=1,
        chunk_count=0,
    )
    chunk = SourceChunk(
        file_path="data/raw/vllm-0.10.1/README.md",
        first_character_index=0,
        last_character_index=4,
        chunk_type="text",
        text="vLLM",
    )
    file = IndexedFile(
        file_path=chunk.file_path,
        content_hash="0" * 64,
        byte_count=4,
        character_count=4,
    )

    with pytest.raises(ValidationError, match="chunk_count"):
        LexicalIndexBuild(metadata=metadata, chunks=[chunk], files=[file])


def test_lexical_index_metadata_rejects_size_above_subject_cap() -> None:
    """The configured chunk size cannot exceed the subject's 2000-char cap."""
    with pytest.raises(ValidationError, match="less than or equal to 2000"):
        LexicalIndexMetadata(
            corpus_path="data/raw/vllm-0.10.1",
            max_chunk_size=2001,
            document_count=0,
            chunk_count=0,
        )


def test_lexical_index_build_rejects_chunk_above_configured_size() -> None:
    """A persisted source span cannot exceed its captured chunk-size limit."""
    metadata = LexicalIndexMetadata(
        corpus_path="data/raw/vllm-0.10.1",
        max_chunk_size=4,
        document_count=1,
        chunk_count=1,
    )
    chunk = SourceChunk(
        file_path="data/raw/vllm-0.10.1/README.md",
        first_character_index=0,
        last_character_index=5,
        chunk_type="text",
        text="vLLM!",
    )
    file = IndexedFile(
        file_path=chunk.file_path,
        content_hash="0" * 64,
        byte_count=5,
        character_count=5,
    )

    with pytest.raises(ValidationError, match="max_chunk_size"):
        LexicalIndexBuild(metadata=metadata, chunks=[chunk], files=[file])


def test_dataset_accepts_unanswered_and_answered_questions() -> None:
    """The subject dataset wrapper can carry public answer ground truth."""
    source = MinimalSource(
        file_path="data/raw/vllm-0.10.1/docs/index.md",
        first_character_index=0,
        last_character_index=100,
    )
    dataset = RagDataset(
        rag_questions=[
            UnansweredQuestion(question_id="q1", question="What is vLLM?"),
            AnsweredQuestion(
                question_id="q2",
                question="Where is scheduling documented?",
                sources=[source],
                answer="In the scheduler documentation.",
            ),
        ]
    )

    dumped = dataset.model_dump()

    assert dumped["rag_questions"][0] == {
        "question_id": "q1",
        "question": "What is vLLM?",
    }
    assert dumped["rag_questions"][1]["sources"] == [source.model_dump()]


def test_student_search_results_round_trip_json() -> None:
    """Batch search output should round-trip through JSON unchanged."""
    result = MinimalSearchResults(
        question_id="q1",
        question="What is paged attention?",
        retrieved_sources=[
            MinimalSource(
                file_path="data/raw/vllm-0.10.1/docs/paged_attention.md",
                first_character_index=5,
                last_character_index=75,
            )
        ],
    )
    batch = StudentSearchResults(search_results=[result], k=10)

    dumped_json = batch.model_dump_json()
    reloaded = StudentSearchResults.model_validate_json(dumped_json)

    assert reloaded == batch
    assert json.loads(dumped_json) == {
        "search_results": [result.model_dump()],
        "k": 10,
    }


def test_student_answer_results_preserve_sources_and_answer() -> None:
    """Answer output keeps retrieved source metadata with each answer."""
    answer = MinimalAnswer(
        question_id="q1",
        question="What is vLLM?",
        retrieved_sources=[
            MinimalSource(
                file_path="data/raw/vllm-0.10.1/README.md",
                first_character_index=0,
                last_character_index=50,
            )
        ],
        answer="vLLM is an inference and serving engine.",
    )
    batch = StudentSearchResultsAndAnswer(search_results=[answer], k=5)

    assert json.loads(batch.model_dump_json()) == {
        "search_results": [answer.model_dump()],
        "k": 5,
    }


def test_student_batches_reject_negative_k() -> None:
    """Top-k metadata should not be negative."""
    with pytest.raises(ValidationError):
        StudentSearchResults(search_results=[], k=-1)
    with pytest.raises(ValidationError):
        StudentSearchResultsAndAnswer(search_results=[], k=-1)
