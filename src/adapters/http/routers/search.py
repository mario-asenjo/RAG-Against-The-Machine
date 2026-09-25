"""Local search controller."""

from typing import Annotated

from fastapi import APIRouter, Depends

from src.adapters.http.dependencies import get_application
from src.adapters.http.models import ApiError, SearchRequest
from src.application.use_cases import RagApplication
from src.domain import MinimalSearchResults

router = APIRouter()


@router.post(
    "/search",
    response_model=MinimalSearchResults,
    responses={
        400: {"model": ApiError},
        404: {"model": ApiError},
        500: {"model": ApiError},
    },
)
def search(
    request: SearchRequest,
    application: Annotated[RagApplication, Depends(get_application)],
) -> MinimalSearchResults:
    """Retrieve exact local source locations synchronously."""
    return application.search(request.query, request, show_progress=False)
