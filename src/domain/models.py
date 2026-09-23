"""Pydantic contracts shared by the RAG pipeline stages."""

from __future__ import annotations

from typing import Literal
from uuid import uuid4

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


class LexicalIndexMetadata(BaseModel):
    """Stable metadata persisted with the lexical retrieval index."""

    schema_version: Literal[2] = 2
    retrieval_method: Literal["sqlite-fts5-bm25"] = "sqlite-fts5-bm25"
    corpus_path: str
    max_chunk_size: int = Field(gt=0, le=2000)
    document_count: int = Field(ge=0)
    chunk_count: int = Field(ge=0)
    index_revision: int = Field(default=1, ge=1)


class IndexedFile(BaseModel):
    """Content identity for one accepted corpus file."""

    file_path: str
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(ge=0)
    character_count: int = Field(ge=0)


class LexicalIndexBuild(BaseModel):
    """Pydantic exchange model between indexing and persistence stages."""

    metadata: LexicalIndexMetadata
    chunks: list[SourceChunk]
    files: list[IndexedFile]

    @model_validator(mode="after")
    def validate_chunks(self) -> "LexicalIndexBuild":
        """Keep persisted chunks aligned with their captured metadata."""
        if self.metadata.chunk_count != len(self.chunks):
            raise ValueError("chunk_count must match the number of chunks")
        if any(
            len(chunk.text) > self.metadata.max_chunk_size
            for chunk in self.chunks
        ):
            raise ValueError("chunk text must not exceed max_chunk_size")
        if self.metadata.document_count != len(self.files):
            raise ValueError("document_count must match the file manifest")
        if len({item.file_path for item in self.files}) != len(self.files):
            raise ValueError("file manifest paths must be unique")
        file_paths = {item.file_path for item in self.files}
        if any(chunk.file_path not in file_paths for chunk in self.chunks):
            raise ValueError("every chunk must belong to the file manifest")
        return self


class LexicalIndexUpdate(BaseModel):
    """Validated delta between a persisted index and the current corpus."""

    metadata: LexicalIndexMetadata
    files: list[IndexedFile]
    changed_paths: list[str]
    removed_paths: list[str]
    changed_chunks: list[SourceChunk]
    reused_file_count: int = Field(ge=0)

    @property
    def has_changes(self) -> bool:
        """Return whether persistence must replace the existing index."""
        return bool(self.changed_paths or self.removed_paths)

    @model_validator(mode="after")
    def validate_update(self) -> "LexicalIndexUpdate":
        """Keep delta paths and final aggregate metadata coherent."""
        file_paths = [item.file_path for item in self.files]
        if self.metadata.document_count != len(file_paths):
            raise ValueError("document_count must match the update manifest")
        if len(set(file_paths)) != len(file_paths):
            raise ValueError("update manifest paths must be unique")
        if any(path not in file_paths for path in self.changed_paths):
            raise ValueError("changed paths must exist in the final manifest")
        if any(path in file_paths for path in self.removed_paths):
            raise ValueError(
                "removed paths must not exist in the final manifest"
            )
        if any(
            chunk.file_path not in self.changed_paths
            for chunk in self.changed_chunks
        ):
            raise ValueError("changed chunks must belong to changed paths")
        return self


class SemanticIndexMetadata(BaseModel):
    """Validated configuration and lifecycle identity for embeddings."""

    schema_version: Literal[1] = 1
    model_name: str
    model_revision: str
    pooling: Literal["attention-mask-mean-l2"] = "attention-mask-mean-l2"
    max_length: int = Field(gt=0)
    embedding_dimension: int = Field(gt=0)
    chunk_count: int = Field(ge=0)
    source_index_revision: int = Field(ge=1)


class UnansweredQuestion(BaseModel):
    """A dataset question before retrieval or answer generation."""

    question_id: str = Field(default_factory=lambda: str(uuid4()))
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
