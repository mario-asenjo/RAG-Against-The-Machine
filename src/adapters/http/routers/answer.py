"""Local answer controller."""

from typing import Annotated

from fastapi import APIRouter, Depends

from src.adapters.http.dependencies import get_application
from src.adapters.http.models import AnswerRequest, ApiError
from src.application.use_cases import RagApplication
from src.domain import MinimalAnswer

router = APIRouter()


@router.post(
    "/answer",
    response_model=MinimalAnswer,
    responses={
        400: {"model": ApiError},
        404: {"model": ApiError},
        500: {"model": ApiError},
    },
)
def answer(
    request: AnswerRequest,
    application: Annotated[RagApplication, Depends(get_application)],
) -> MinimalAnswer:
    """Generate one grounded local answer synchronously."""
    return application.answer(request.query, request, show_progress=False)
