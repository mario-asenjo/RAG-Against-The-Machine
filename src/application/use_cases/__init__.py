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
from src.application.use_cases.fuse_retrieval import fuse_ranked_sources
from src.application.use_cases.pipeline import RagApplication
from src.application.use_cases.update_index import plan_lexical_index_update

__all__ = [
    "ABSTENTION_ANSWER",
    "AnswerGeneration",
    "DatasetError",
    "EvaluationConfigurationError",
    "StudentDataError",
    "RagApplication",
    "answer_search_result",
    "build_lexical_index",
    "evaluate_search_results",
    "fuse_ranked_sources",
    "plan_lexical_index_update",
]
