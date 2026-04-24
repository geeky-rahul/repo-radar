"""
Async GitHub Search API tool.
Accepts a ParsedGitHubQuery and returns a list of raw RepositoryItem objects.
"""
from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import get_settings
from app.core.exceptions import GitHubAPIError, GitHubRateLimitError
from app.core.logging import get_logger
from app.schemas.search import ParsedGitHubQuery, RepositoryItem

logger = get_logger(__name__)

_GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"


def _build_github_query(parsed: ParsedGitHubQuery) -> str:
    """Assemble GitHub search qualifier string from parsed fields."""
    parts: list[str] = [parsed.query.strip()]

    if parsed.language:
        safe_lang = parsed.language.replace(" ", "").replace("#", "sharp").replace("+", "p")
        parts.append(f"language:{safe_lang}")

    if parsed.min_stars and parsed.min_stars > 0:
        parts.append(f"stars:>={parsed.min_stars}")

    if parsed.pushed_after:
        parts.append(f"pushed:>={parsed.pushed_after}")

    if parsed.fork is True:
        parts.append("fork:true")
    elif parsed.fork is False:
        parts.append("fork:false")

    if parsed.archived is True:
        parts.append("archived:true")
    elif parsed.archived is False:
        parts.append("archived:false")

    if parsed.topic:
        topic_value = parsed.topic.strip()
        if topic_value:
            parts.append(f"topic:{topic_value}")

    if parsed.license:
        license_value = parsed.license.strip()
        if license_value:
            parts.append(f"license:{license_value}")

    return " ".join(parts)


def _parse_repository(raw: dict[str, Any]) -> RepositoryItem:
    owner = raw.get("owner", {})
    license_info = raw.get("license") or {}
    return RepositoryItem(
        id=raw["id"],
        name=raw["name"],
        full_name=raw["full_name"],
        html_url=raw["html_url"],
        description=raw.get("description"),
        stargazers_count=raw.get("stargazers_count", 0),
        forks_count=raw.get("forks_count", 0),
        open_issues_count=raw.get("open_issues_count", 0),
        language=raw.get("language"),
        pushed_at=raw.get("pushed_at"),
        created_at=raw.get("created_at"),
        topics=raw.get("topics", []),
        license_name=license_info.get("name"),
        archived=raw.get("archived", False),
        owner_login=owner.get("login", ""),
        owner_avatar_url=owner.get("avatar_url"),
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(httpx.TransportError),
    reraise=True,
)
async def search_github_repositories(
    parsed_query: ParsedGitHubQuery,
    top_k: int = 10,
) -> list[RepositoryItem]:
    settings = get_settings()
    github_query = _build_github_query(parsed_query)

    headers: dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"

    params: dict[str, Any] = {
        "q": github_query,
        "sort": "stars",
        "order": "desc",
        "per_page": min(top_k, settings.github_search_max_results),
        "page": 1,
    }

    logger.info("github.search", query=github_query, params=params)

    async with httpx.AsyncClient(timeout=settings.github_request_timeout) as client:
        try:
            response = await client.get(_GITHUB_SEARCH_URL, headers=headers, params=params)
        except httpx.TimeoutException as exc:
            raise GitHubAPIError("GitHub API request timed out") from exc
        except httpx.TransportError as exc:
            raise GitHubAPIError(f"Network error contacting GitHub: {exc}") from exc

        if response.status_code == 403 and "rate limit" in response.text.lower():
            raise GitHubRateLimitError(
                "GitHub API rate limit exceeded",
                {"reset": response.headers.get("X-RateLimit-Reset")},
            )

        if response.status_code == 422:
            raise GitHubAPIError(
                "Invalid GitHub search query",
                {"query": github_query, "detail": response.json()},
            )

        if response.status_code != 200:
            raise GitHubAPIError(
                f"GitHub API returned {response.status_code}",
                {"body": response.text[:500]},
            )

        data = response.json()
        items: list[RepositoryItem] = [
            _parse_repository(item) for item in data.get("items", [])
        ]

        logger.info(
            "github.search_done",
            total_count=data.get("total_count", 0),
            returned=len(items),
        )
        return items
