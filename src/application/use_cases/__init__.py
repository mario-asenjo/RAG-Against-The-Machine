"""Application use cases added one vertical slice at a time."""

from src.application.use_cases.answer_question import (
    ABSTENTION_ANSWER,
    AnswerGeneration,
    answer_search_result,
)
from src.application.use_cases.build_index import build_lexical_index
from src.application.use_cases.evaluate_recall import (
    DatasetError,
    EvaluationConfigurationError,
    StudentDataError,
    evaluate_search_results,
)

__all__ = [
    "ABSTENTION_ANSWER",
    "AnswerGeneration",
    "DatasetError",
    "EvaluationConfigurationError",
    "StudentDataError",
    "answer_search_result",
    "build_lexical_index",
    "evaluate_search_results",
]
