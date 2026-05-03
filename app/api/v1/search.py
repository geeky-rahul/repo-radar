from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, Query, status

from app.core.exceptions import (
    GitHubAPIError,
    GitHubRateLimitError,
    LLMError,
    QueryParsingError,
)
from app.core.logging import get_logger
from app.schemas.search import ErrorDetail, ErrorResponse, ParsedGitHubQuery, SearchRequest, SearchResponse
from app.services.ranking import rank_repositories
from app.services.search import execute_search
from app.tools.github_search import search_github_repositories

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


@router.get(
    "/rising",
    response_model=SearchResponse,
    summary="Get rising projects trending by recent star growth",
    description=(
        "Fetches a broad set of GitHub repositories and ranks them using recent star "
        "growth, fork momentum, and contributor activity."
    ),
)
async def rising_repositories(top_k: int = Query(10, ge=1, le=30, description="Number of rising repositories to return")) -> SearchResponse:
    start = time.monotonic()
    parsed = ParsedGitHubQuery(query="stars:>10")
    repos = await search_github_repositories(parsed, top_k=top_k)
    ranked = rank_repositories(repos)
    duration_ms = round((time.monotonic() - start) * 1000, 2)
    return SearchResponse(
        original_query="rising projects",
        parsed_query=parsed,
        total_found=len(ranked),
        results=ranked[: top_k],
        cached=False,
        duration_ms=duration_ms,
    )
