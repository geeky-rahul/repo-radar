from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.core.exceptions import (
    GitHubAPIError,
    GitHubRateLimitError,
    LLMError,
    QueryParsingError,
)
from app.core.logging import get_logger
from app.schemas.search import ErrorDetail, ErrorResponse, SearchRequest, SearchResponse
from app.services.search import execute_search

router = APIRouter(prefix="/search", tags=["search"])
logger = get_logger(__name__)


@router.post(
    "/repositories",
    response_model=SearchResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad request / parse error"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        429: {"model": ErrorResponse, "description": "GitHub rate limit exceeded"},
        502: {"model": ErrorResponse, "description": "GitHub API error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Search GitHub repositories using natural language",
    description=(
        "Converts a natural language query into an optimised GitHub search, "
        "fetches repositories, ranks them, and returns structured results."
    ),
)
async def search_repositories(request: SearchRequest) -> SearchResponse:
    logger.info("api.search", query=request.query, top_k=request.top_k)

    try:
        return await execute_search(request)

    except GitHubRateLimitError as exc:
        logger.warning("api.rate_limit", details=exc.details)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=ErrorDetail(
                code="GITHUB_RATE_LIMIT",
                message=exc.message,
                details=exc.details,
            ).model_dump(),
        )

    except GitHubAPIError as exc:
        logger.error("api.github_error", error=exc.message, details=exc.details)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=ErrorDetail(
                code="GITHUB_API_ERROR",
                message=exc.message,
                details=exc.details,
            ).model_dump(),
        )

    except QueryParsingError as exc:
        logger.error("api.parse_error", error=exc.message)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorDetail(
                code="QUERY_PARSE_ERROR",
                message=exc.message,
                details=exc.details,
            ).model_dump(),
        )

    except LLMError as exc:
        logger.error("api.llm_error", error=exc.message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorDetail(
                code="LLM_ERROR",
                message=exc.message,
            ).model_dump(),
        )

    except Exception as exc:
        logger.exception("api.unhandled_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorDetail(
                code="INTERNAL_ERROR",
                message="An unexpected error occurred",
            ).model_dump(),
        )
