"""Pydantic contracts shared by the RAG pipeline stages."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class MinimalSource(BaseModel):
    """A source span in the original corpus text."""

    file_path: str
    first_character_index: int = Field(ge=0)
    last_character_index: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_range(self) -> "MinimalSource":
        """Reject inverted source ranges."""
        if self.last_character_index < self.first_character_index:
            raise ValueError(
                "last_character_index must be greater than or equal to "
                "first_character_index"
            )
        return self


class SourceDocument(BaseModel):
    """An accepted corpus file with its exact original text."""

    file_path: str
    text: str


class SourceChunk(MinimalSource):
    """A half-open source span plus its exact text slice."""

    chunk_type: Literal["python", "text"]
    text: str

    @model_validator(mode="after")
    def validate_text_width(self) -> "SourceChunk":
        """Keep chunk text length aligned with the half-open source span."""
        expected_width = self.last_character_index - self.first_character_index
        if len(self.text) != expected_width:
            raise ValueError("text length must match source span width")
        return self


class UnansweredQuestion(BaseModel):
    """A dataset question before retrieval or answer generation."""

    question_id: str
    question: str


class AnsweredQuestion(UnansweredQuestion):
    """A dataset question with ground-truth or generated answer data."""

    sources: list[MinimalSource]
    answer: str


class RagDataset(BaseModel):
    """A dataset wrapper matching the subject JSON container."""

    rag_questions: list[UnansweredQuestion | AnsweredQuestion]


class MinimalSearchResults(UnansweredQuestion):
    """Retrieved source spans for one question."""

    retrieved_sources: list[MinimalSource]


class MinimalAnswer(MinimalSearchResults):
    """Retrieved sources and generated answer for one question."""

    answer: str


class StudentSearchResults(BaseModel):
    """Batch search output produced by the student implementation."""

    search_results: list[MinimalSearchResults]
    k: int = Field(ge=0)


class StudentSearchResultsAndAnswer(BaseModel):
    """Batch search-and-answer output produced by the implementation."""

    search_results: list[MinimalAnswer]
    k: int = Field(ge=0)
