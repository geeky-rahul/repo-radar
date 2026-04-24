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
        score += 0.45
    if repo.topics:
        score += 0.20
    if repo.license_name:
        score += 0.15
    if repo.language:
        score += 0.10
    if repo.owner_login:
        score += 0.10
    return min(score, 1.0)


def _contributor_activity_score(repo: RepositoryItem) -> float:
    """Estimate contributor activity from recent pushes and fork adoption."""
    if repo.archived:
        return 0.0

    recency = _recency_score(repo.pushed_at)
    forks = min(repo.forks_count / 1000.0, 1.0)
    return 0.6 * recency + 0.4 * forks


def _ci_presence_score(repo: RepositoryItem) -> float:
    """Detect CI/CD readiness from repository topics."""
    if not repo.topics:
        return 0.0
    ci_tags = {topic.lower() for topic in repo.topics}
    if ci_tags & {"ci", "github-actions", "workflow", "actions", "pipeline", "build"}:
        return 1.0
    return 0.0


def _community_health_score(repo: RepositoryItem) -> float:
    """Infer community health from issue pressure and CI/CD signals."""
    if repo.archived:
        return 0.0

    issue_pressure = min(repo.open_issues_count / 50.0, 1.0)
    issue_health = max(0.0, 1.0 - issue_pressure)
    ci_score = _ci_presence_score(repo)
    return 0.7 * issue_health + 0.3 * ci_score


def _trend_score(repo: RepositoryItem) -> float:
    """Estimate momentum using stars per day over repository lifetime."""
    if not repo.created_at or repo.stargazers_count <= 0:
        return 0.0

    try:
        created = datetime.fromisoformat(repo.created_at.replace("Z", "+00:00"))
    except ValueError:
        return 0.0

    age_days = max((datetime.now(tz=timezone.utc) - created).days, 1)
    velocity = repo.stargazers_count / age_days
    return min(1.0, velocity / 50.0)


def rank_repositories(repos: list[RepositoryItem]) -> list[RepositoryItem]:
    if not repos:
        return repos

    settings = get_settings()
    w_stars = settings.ranking_stars_weight
    w_recency = settings.ranking_recency_weight
    w_completeness = settings.ranking_completeness_weight
    w_activity = settings.ranking_activity_weight
    w_health = settings.ranking_health_weight
    w_trend = settings.ranking_trend_weight

    ranked: list[RepositoryItem] = []
    for repo in repos:
        score = (
            w_stars * _stars_score(repo.stargazers_count)
            + w_recency * _recency_score(repo.pushed_at)
            + w_completeness * _completeness_score(repo)
            + w_activity * _contributor_activity_score(repo)
            + w_health * _community_health_score(repo)
            + w_trend * _trend_score(repo)
        )
        ranked.append(repo.model_copy(update={"score": round(score, 6)}))

    ranked.sort(key=lambda r: r.score, reverse=True)
    logger.debug("ranking.done", count=len(ranked), top_score=ranked[0].score if ranked else 0)
    return ranked
