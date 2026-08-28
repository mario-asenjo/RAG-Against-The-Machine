"""Domain contracts for the RAG pipeline."""

from src.domain.models import (
    AnsweredQuestion,
    LexicalIndexBuild,
    LexicalIndexMetadata,
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
    "LexicalIndexBuild",
    "LexicalIndexMetadata",
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
