"""Domain contracts for the RAG pipeline."""

from src.domain.models import (
    AnsweredQuestion,
    IndexedFile,
    LexicalIndexBuild,
    LexicalIndexMetadata,
    LexicalIndexUpdate,
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
    "IndexedFile",
    "LexicalIndexBuild",
    "LexicalIndexMetadata",
    "LexicalIndexUpdate",
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
