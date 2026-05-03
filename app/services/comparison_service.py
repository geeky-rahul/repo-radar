"""Repository comparison orchestration."""
from __future__ import annotations

import asyncio

from app.core.logging import get_logger
from app.schemas.intelligence import ComparisonRepositoryRow, ComparisonRequest, ComparisonResponse
from app.schemas.search import RepositoryItem
from app.schemas.search import ParsedGitHubQuery
from app.services.personalization_service import evaluate_fit
from app.services.scoring_service import assess_repository_quality, build_lightweight_signals
from app.tools.github_search import search_github_repositories

logger = get_logger(__name__)


async def _fetch_repo(full_name: str) -> RepositoryItem:
    parsed = ParsedGitHubQuery(query=f"repo:{full_name}")
    repos = await search_github_repositories(parsed, top_k=5)
    exact = next((repo for repo in repos if repo.full_name.lower() == full_name.lower()), None)
    if exact:
        return exact
    if repos:
        return repos[0]
    raise ValueError(f"Repository not found: {full_name}")


def _complexity_from_signals(repo: RepositoryItem, signals) -> str:
    if signals.documentation_quality >= 0.7 and signals.dependency_freshness >= 0.55 and signals.open_issue_backlog_ratio < 0.35:
        return "Beginner"
    if signals.documentation_quality >= 0.45 or repo.language in {"Python", "JavaScript", "TypeScript"}:
        return "Intermediate"
    return "Advanced"


def _row_from_repo(repo: RepositoryItem, signals, intent) -> ComparisonRepositoryRow:
    quality = assess_repository_quality(repo, signals)
    fit = evaluate_fit(repo, intent, signals)
    community_activity = "High" if signals.recent_commits_30d >= 15 else "Moderate" if signals.recent_commits_30d >= 5 else "Low"
    complexity = _complexity_from_signals(repo, signals)
    setup_difficulty = "Low" if complexity == "Beginner" else "Moderate" if complexity == "Intermediate" else "High"
    return ComparisonRepositoryRow(
        full_name=repo.full_name,
        language=repo.language,
        quality_score=quality.score,
        fit_score=fit.score if fit else quality.score,
        documentation_quality=signals.documentation_quality,
        maintenance_status=quality.label,
        community_activity=community_activity,
        setup_difficulty=setup_difficulty,
        use_case_suitability=complexity,
        label=quality.label,
        insight=quality.insight,
    )


async def compare_repositories(request: ComparisonRequest) -> ComparisonResponse:
    repo_items = await asyncio.gather(*(_fetch_repo(full_name) for full_name in request.repositories))
    signals_list = [build_lightweight_signals(repo) for repo in repo_items]

    rows: list[ComparisonRepositoryRow] = []
    for repo, signals in zip(repo_items, signals_list, strict=False):
        rows.append(_row_from_repo(repo, signals, request.intent))

    best_for_beginners = max(rows, key=lambda row: (row.fit_score, row.documentation_quality), default=None)
    best_for_production = max(rows, key=lambda row: (row.quality_score, row.documentation_quality), default=None)
    most_active = max(rows, key=lambda row: (row.community_activity == "High", row.quality_score), default=None)

    if best_for_beginners and best_for_production and most_active:
        conclusion = (
            f"Best for beginners: {best_for_beginners.full_name}. "
            f"Best for production: {best_for_production.full_name}. "
            f"Most actively maintained: {most_active.full_name}."
        )
    else:
        conclusion = "Comparison completed, but not enough signal was available to identify clear winners."

    logger.info("comparison.done", count=len(rows))
    return ComparisonResponse(
        repositories=rows,
        conclusion=conclusion,
        best_for_beginners=best_for_beginners.full_name if best_for_beginners else None,
        best_for_production=best_for_production.full_name if best_for_production else None,
        most_active=most_active.full_name if most_active else None,
    )
