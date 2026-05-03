"""
Search service — orchestrates the full pipeline:
  1. Check cache
  2. Parse natural-language query (LLM → fallback)
  3. Apply user overrides (language, min_stars, pushed_after)
  4. Fetch from GitHub
  5. Rank results
  6. Cache and return
"""
from __future__ import annotations

import time

from app.agents.query_agent import parse_query
from app.core.logging import get_logger
from app.schemas.search import (
    ParsedGitHubQuery,
    SearchRequest,
    SearchResponse,
)
from app.services.cache import cache_get, cache_set, get_repo_star_history, update_repo_star_history
from app.services.ranking import rank_repositories
from app.tools.github_search import search_github_repositories

logger = get_logger(__name__)

_CACHE_NAMESPACE = "search_v1"


def _apply_overrides(parsed: ParsedGitHubQuery, request: SearchRequest) -> ParsedGitHubQuery:
    """User-supplied overrides always win over LLM inference."""
    overrides: dict = {}
    if request.language is not None:
        overrides["language"] = request.language
    if request.min_stars is not None:
        overrides["min_stars"] = request.min_stars
    if request.pushed_after is not None:
        overrides["pushed_after"] = request.pushed_after
    if request.fork is not None:
        overrides["fork"] = request.fork
    if request.archived is not None:
        overrides["archived"] = request.archived
    if request.topic is not None:
        overrides["topic"] = request.topic
    if request.license is not None:
        overrides["license"] = request.license
    if overrides:
        return parsed.model_copy(update=overrides)
    return parsed


async def execute_search(request: SearchRequest) -> SearchResponse:
    t0 = time.monotonic()

    cache_key_payload = request.model_dump()

    # 1. Cache lookup
    cached_data = await cache_get(_CACHE_NAMESPACE, cache_key_payload)
    if cached_data:
        response = SearchResponse.model_validate(cached_data)
        response.cached = True
        response.duration_ms = round((time.monotonic() - t0) * 1000, 2)
        return response

    # 2. Parse query
    parsed = await parse_query(request.query)

    # 3. Apply user overrides
    parsed = _apply_overrides(parsed, request)
    logger.info("search.parsed_query", parsed=parsed.model_dump())

    # 4. Fetch from GitHub
    repos = await search_github_repositories(parsed, top_k=request.top_k)

    # 4.1 Attach stored star history for better trend scoring
    for repo in repos:
        history = await get_repo_star_history(repo.id)
        if history and isinstance(history.get("previous"), int):
            repo.stars_yesterday = history["previous"]

    # 5. Rank
    ranked = rank_repositories(repos)

    # 5.1 Persist star history for future trend calculations
    for repo in repos:
        await update_repo_star_history(repo.id, repo.stargazers_count)

    # 6. Build response
    duration_ms = round((time.monotonic() - t0) * 1000, 2)
    response = SearchResponse(
        original_query=request.query,
        parsed_query=parsed,
        total_found=len(ranked),
        results=ranked[: request.top_k],
        cached=False,
        duration_ms=duration_ms,
    )

    # 7. Store in cache (fire-and-forget style)
    await cache_set(_CACHE_NAMESPACE, cache_key_payload, response.model_dump())

    return response
