from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query

from app.core.logging import get_logger
from app.schemas.search import ParsedGitHubQuery, SearchResponse, RepositoryItem
from app.services.cache import get_redis
from app.services.ranking import rank_repositories
from app.tools.github_search import search_github_repositories

router = APIRouter(prefix="/trending", tags=["trending"])
logger = get_logger(__name__)

CACHE_KEY = "repo_search:trending_repos"
CACHE_TTL = 900  # 15 minutes


@router.get(
    "/repositories",
    response_model=SearchResponse,
    summary="Get trending repositories",
    description="Fetches repositories gaining traction right now using custom scoring and caching.",
)
async def trending_repositories(top_k: int = Query(10, ge=1, le=30)) -> SearchResponse:
    start_time = time.monotonic()
    
    redis = await get_redis()
    
    # Try cache first
    cached_data = await redis.get(CACHE_KEY)
    if cached_data:
        try:
            cached_json = json.loads(cached_data)
            # Ensure we only return up to top_k
            results = [RepositoryItem(**r) for r in cached_json["results"]][:top_k]
            duration_ms = round((time.monotonic() - start_time) * 1000, 2)
            
            return SearchResponse(
                original_query="trending projects",
                parsed_query=ParsedGitHubQuery(query="trending custom"),
                total_found=len(results),
                results=results,
                cached=True,
                duration_ms=duration_ms,
            )
        except Exception as e:
            logger.warning("api.trending.cache_parse_error", error=str(e))
    
    # If not cached, query GitHub
    # We want repositories pushed in the last 7 days with at least 50 stars
    last_week = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    query_str = f"pushed:>{last_week} stars:>50"
    
    parsed = ParsedGitHubQuery(
        query=query_str,
        language=None,
        min_stars=50,
        pushed_after=last_week
    )
    
    # Fetch more than we need to rank them properly
    repos = await search_github_repositories(parsed, top_k=50)
    
    # Use our robust ranking service to find the actual "trending" ones
    ranked = rank_repositories(repos)
    top_results = ranked[:30]  # Store up to 30 in cache
    
    # Cache the results
    cache_payload = {
        "results": [r.model_dump(mode="json") for r in top_results]
    }
    await redis.setex(CACHE_KEY, CACHE_TTL, json.dumps(cache_payload))
    
    duration_ms = round((time.monotonic() - start_time) * 1000, 2)
    
    return SearchResponse(
        original_query="trending projects",
        parsed_query=parsed,
        total_found=len(top_results),
        results=top_results[:top_k],
        cached=False,
        duration_ms=duration_ms,
    )
