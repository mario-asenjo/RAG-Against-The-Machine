"""Local index controller."""

from typing import Annotated

from fastapi import APIRouter, Depends

from src.adapters.http.dependencies import get_application
from src.adapters.http.models import ApiError, IndexRequest
from src.application.models import IndexOperationResult
from src.application.use_cases import RagApplication

router = APIRouter()


@router.post(
    "/index",
    response_model=IndexOperationResult,
    responses={
        400: {"model": ApiError},
        404: {"model": ApiError},
        500: {"model": ApiError},
    },
)
def index(
    request: IndexRequest,
    application: Annotated[RagApplication, Depends(get_application)],
) -> IndexOperationResult:
    """Build or update local indexes synchronously."""
    return application.index(request, show_progress=False)
