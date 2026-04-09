"""
Repository ranking service.

Computes a composite score for each repository and returns them sorted
in descending order. Scoring is fully deterministic and config-driven.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.search import RepositoryItem

logger = get_logger(__name__)

_MAX_STARS_CAP = 200_000  # prevent log from exploding on mega-repos


def _stars_score(stars: int) -> float:
    """Log-normalised star score in [0, 1]."""
    if stars <= 0:
        return 0.0
    return math.log1p(min(stars, _MAX_STARS_CAP)) / math.log1p(_MAX_STARS_CAP)


def _recency_score(pushed_at: str | None) -> float:
    """Score based on last push date; decays exponentially over ~2 years."""
    if not pushed_at:
        return 0.0
    try:
        pushed = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    now = datetime.now(tz=timezone.utc)
    days_ago = max((now - pushed).days, 0)
    # e^(-days/730) → 1.0 if pushed today, ~0.5 after 1 year, ~0.25 after 2 years
    return math.exp(-days_ago / 730)


def _completeness_score(repo: RepositoryItem) -> float:
    """Bonus for metadata completeness."""
    score = 0.0
    if repo.description and len(repo.description.strip()) > 10:
        score += 0.5
    if repo.topics:
        score += 0.25
    if repo.license_name:
        score += 0.15
    if repo.language:
        score += 0.10
    return min(score, 1.0)


def rank_repositories(repos: list[RepositoryItem]) -> list[RepositoryItem]:
    if not repos:
        return repos

    settings = get_settings()
    w_stars = settings.ranking_stars_weight
    w_recency = settings.ranking_recency_weight
    w_completeness = settings.ranking_completeness_weight

    ranked: list[RepositoryItem] = []
    for repo in repos:
        score = (
            w_stars * _stars_score(repo.stargazers_count)
            + w_recency * _recency_score(repo.pushed_at)
            + w_completeness * _completeness_score(repo)
        )
        # Return a new instance so original list is unmodified
        ranked.append(repo.model_copy(update={"score": round(score, 6)}))

    ranked.sort(key=lambda r: r.score, reverse=True)
    logger.debug("ranking.done", count=len(ranked), top_score=ranked[0].score if ranked else 0)
    return ranked
