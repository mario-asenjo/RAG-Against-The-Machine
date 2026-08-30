"""Application use cases added one vertical slice at a time."""

from src.application.use_cases.build_index import build_lexical_index
from src.application.use_cases.evaluate_recall import (
    DatasetError,
    EvaluationConfigurationError,
    StudentDataError,
    evaluate_search_results,
)

__all__ = [
    "DatasetError",
    "EvaluationConfigurationError",
    "StudentDataError",
    "build_lexical_index",
    "evaluate_search_results",
]
