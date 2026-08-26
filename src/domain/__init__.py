"""Domain contracts for the RAG pipeline."""

from src.domain.models import (
    AnsweredQuestion,
    MinimalAnswer,
    MinimalSearchResults,
    MinimalSource,
    SourceChunk,
    RagDataset,
    SourceDocument,
    StudentSearchResults,
    StudentSearchResultsAndAnswer,
    UnansweredQuestion,
)

__all__ = [
    "AnsweredQuestion",
    "MinimalAnswer",
    "MinimalSearchResults",
    "MinimalSource",
    "SourceChunk",
    "RagDataset",
    "SourceDocument",
    "StudentSearchResults",
    "StudentSearchResultsAndAnswer",
    "UnansweredQuestion",
]
