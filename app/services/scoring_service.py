"""Deterministic repository quality scoring and refinement suggestions."""
from __future__ import annotations

from datetime import datetime, timezone
import math

from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.intelligence import (
    PersonalizationIntent,
    QueryRefinementSuggestion,
    RepositoryDeepSignals,
    RepositoryFitAssessment,
    RepositoryIntelligence,
    RepositoryQualityAssessment,
    RepositorySummary,
)
from app.schemas.search import ParsedGitHubQuery, RepositoryItem, SearchRequest

logger = get_logger(__name__)

_MAX_STARS_CAP = 200_000


def build_lightweight_signals(repo: RepositoryItem) -> RepositoryDeepSignals:
    readme_words = len((repo.description or "").split()) * 20
    doc_quality = 0.2
    if repo.description:
        doc_quality += 0.25
    if repo.topics:
        doc_quality += 0.15
    if repo.license_name:
        doc_quality += 0.1
    if repo.language:
        doc_quality += 0.1
    if repo.pushed_at:
        doc_quality += 0.1

    dependency_freshness = 0.4
    if repo.topics and any(topic.lower() in {"docker", "ci", "github-actions", "workflow"} for topic in repo.topics):
        dependency_freshness += 0.2

    open_issue_backlog_ratio = min(repo.open_issues_count / 150.0, 1.0)

    return RepositoryDeepSignals(
        recent_commits_30d=12 if repo.pushed_at else 0,
        recent_commits_90d=32 if repo.pushed_at else 0,
        contributor_count=max(1, min(repo.forks_count // 10 + 1, 20)),
        issue_resolution_rate=max(0.25, 1.0 - open_issue_backlog_ratio),
        pr_merge_rate=max(0.25, 1.0 - open_issue_backlog_ratio * 0.7),
        release_frequency_per_month=0.5 if repo.pushed_at else 0.0,
        documentation_quality=min(1.0, doc_quality),
        dependency_freshness=min(1.0, dependency_freshness),
        open_issue_backlog_ratio=open_issue_backlog_ratio,
        has_readme=bool(repo.description),
        readme_word_count=readme_words,
        primary_language_count=1 if repo.language else 0,
        architecture_pattern="modular" if repo.topics and len(repo.topics) >= 3 else "monolith",
        entry_points=[],
        key_files=[],
        core_modules=[],
    )


def _stars_score(stars: int) -> float:
    if stars <= 0:
        return 0.0
    return math.log1p(min(stars, _MAX_STARS_CAP)) / math.log1p(_MAX_STARS_CAP)


def _recency_score(pushed_at: str | None) -> float:
    if not pushed_at:
        return 0.0
    try:
        pushed = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    now = datetime.now(tz=timezone.utc)
    days_ago = max((now - pushed).days, 0)
    return math.exp(-days_ago / 730)


def _score_component(value: float, weight: float) -> float:
    return max(0.0, min(1.0, value)) * weight


def quality_label(score: int, archived: bool = False) -> str:
    if archived:
        return "Abandoned"
    if score >= 78:
        return "Highly Active"
    if score >= 55:
        return "Stable but Slow"
    if score >= 30:
        return "At Risk"
    return "Abandoned"


def _trend_label(repo: RepositoryItem, signals: RepositoryDeepSignals) -> tuple[str, str]:
    recency = _recency_score(repo.pushed_at)
    commit_velocity = (signals.recent_commits_30d / 30.0) if signals.recent_commits_30d else 0.0
    stars_velocity = (repo.stargazers_count / max(1, max(signals.recent_commits_90d, 1))) if repo.stargazers_count else 0.0

    if repo.archived:
        return "Declining", "Repository is archived and should not be considered actively maintained."
    if recency > 0.7 and commit_velocity > 0.2:
        return "Rising", "Recent activity suggests healthy ongoing maintenance."
    if recency < 0.25 and commit_velocity < 0.05:
        return "Cooling", "Recent commit activity is limited and the project looks slower to evolve."
    if stars_velocity > 5:
        return "Trending", "Recent attention is high relative to the repository's current activity."
    return "Stable", "Repository activity looks steady but not especially fast-moving."


def _clone_risk_warning(repo: RepositoryItem, signals: RepositoryDeepSignals) -> str | None:
    warnings: list[str] = []
    if repo.archived:
        warnings.append("This repository is archived.")
    if _recency_score(repo.pushed_at) < 0.25:
        warnings.append("No recent commits detected.")
    if signals.open_issue_backlog_ratio > 0.6:
        warnings.append("Open issue backlog is high relative to maintenance activity.")
    if signals.contributor_count <= 2:
        warnings.append("Contributor bus factor looks low.")
    if signals.dependency_freshness < 0.35:
        warnings.append("Dependency freshness appears weak.")
    if not warnings:
        return None
    return "\u26a0\ufe0f This repository shows signs of being unmaintained: " + " ".join(warnings)


def _quality_insight(repo: RepositoryItem, signals: RepositoryDeepSignals, score: int) -> str:
    if repo.archived:
        return "Archived repository; treat this as reference material rather than an actively maintained project."
    if score >= 80 and signals.documentation_quality >= 0.7 and signals.open_issue_backlog_ratio < 0.35:
        return "Strong maintenance, good documentation, and a healthy issue backlog make this a low-risk choice."
    if signals.documentation_quality < 0.4:
        return "Popularity is present, but thin documentation may slow onboarding for new contributors."
    if signals.open_issue_backlog_ratio > 0.55:
        return "The project is still useful, but unresolved issues are accumulating faster than they are being closed."
    if _recency_score(repo.pushed_at) < 0.35:
        return "The repository looks established, but recent maintenance activity has softened."
    return "The repository appears stable with a balanced mix of popularity, maintenance, and onboarding clarity."


def _fit_score(repo: RepositoryItem, signals: RepositoryDeepSignals, intent: PersonalizationIntent | None) -> RepositoryFitAssessment | None:
    if intent is None and not any([signals.documentation_quality, signals.dependency_freshness]):
        return None

    score = 50.0
    explanation_parts: list[str] = []

    if intent is None:
        score += signals.documentation_quality * 12
        score += (1.0 - signals.open_issue_backlog_ratio) * 10
        score += (1.0 if not repo.archived else -20)
        explanation_parts.append("Balanced default fit based on repository quality and maintenance health.")
    else:
        level = (intent.experience_level or "").lower()
        goal = (intent.goal or "").lower()

        if level == "beginner":
            score += signals.documentation_quality * 20
            score += (1.0 - signals.open_issue_backlog_ratio) * 12
            score += 8 if signals.readme_word_count >= 300 else -4
            explanation_parts.append("Good for beginners due to stronger documentation and lower setup friction.")
        elif level == "intermediate":
            score += signals.primary_language_count * 2
            score += signals.documentation_quality * 10
            score += 6 if signals.architecture_pattern in {"modular", "microservices"} else 0
            explanation_parts.append("Intermediate fit due to structured code and a moderate learning curve.")
        elif level == "advanced":
            score += 10 if signals.architecture_pattern in {"microservices", "modular"} else 2
            score += 8 if repo.forks_count > 100 else 2
            explanation_parts.append("Advanced fit because the project has enough complexity to be instructive or production-relevant.")

        if goal == "learning":
            score += signals.documentation_quality * 12
            score += 8 if signals.readme_word_count >= 250 else 0
        elif goal == "production":
            score += (1.0 - signals.open_issue_backlog_ratio) * 14
            score += signals.dependency_freshness * 10
        elif goal == "contribution":
            score += 10 if signals.open_issue_backlog_ratio > 0.15 else 2
            score += 8 if signals.contributor_count >= 3 else 0
        elif goal == "reference":
            score += signals.documentation_quality * 12

        for constraint in intent.constraints:
            lowered = constraint.lower()
            if "lightweight" in lowered or "simple" in lowered:
                score += 6 if signals.architecture_pattern == "library" else 2
            if "no api" in lowered or "no external api" in lowered:
                score += 4
            if "no ml" in lowered:
                score += 4 if repo.language and repo.language.lower() != "python" else 1
            if "paid api" in lowered:
                score += 4

        if intent.experience_level == "beginner" and signals.open_issue_backlog_ratio > 0.45:
            score -= 10

    final_score = int(max(0, min(100, round(score))))
    if not explanation_parts:
        explanation_parts.append("Fit computed from repository metadata and intent alignment.")
    return RepositoryFitAssessment(score=final_score, explanation=" ".join(explanation_parts))


def _maintenance_status(signals: RepositoryDeepSignals, quality_score: int, archived: bool) -> str:
    if archived:
        return "Archived"
    if quality_score >= 78 and signals.open_issue_backlog_ratio < 0.4:
        return "Healthy"
    if quality_score >= 55:
        return "Maintaining"
    if quality_score >= 30:
        return "Watchlist"
    return "At Risk"


def assess_repository_quality(repo: RepositoryItem, signals: RepositoryDeepSignals | None = None) -> RepositoryQualityAssessment:
    signals = signals or build_lightweight_signals(repo)

    stars = _stars_score(repo.stargazers_count)
    activity = 0.6 * _recency_score(repo.pushed_at) + 0.4 * min(1.0, (signals.recent_commits_90d / 50.0) if signals.recent_commits_90d else 0.0)
    bus_factor = min(1.0, signals.contributor_count / 10.0)
    issue_resolution = signals.issue_resolution_rate if signals.issue_resolution_rate is not None else max(0.0, 1.0 - signals.open_issue_backlog_ratio)
    pr_merge = signals.pr_merge_rate if signals.pr_merge_rate is not None else issue_resolution
    releases = min(1.0, signals.release_frequency_per_month / 2.0)
    docs = signals.documentation_quality
    deps = signals.dependency_freshness
    backlog = max(0.0, 1.0 - signals.open_issue_backlog_ratio)

    score = (
        _score_component(stars, 0.18)
        + _score_component(activity, 0.20)
        + _score_component(bus_factor, 0.12)
        + _score_component(issue_resolution, 0.12)
        + _score_component(pr_merge, 0.10)
        + _score_component(releases, 0.08)
        + _score_component(docs, 0.12)
        + _score_component(deps, 0.05)
        + _score_component(backlog, 0.03)
    )

    quality_score = int(round(score * 100))
    label = quality_label(quality_score, archived=repo.archived)
    insight = _quality_insight(repo, signals, quality_score)
    clone_risk = _clone_risk_warning(repo, signals)
    trend_label, trend_note = _trend_label(repo, signals)

    factors = {
        "stars": round(stars, 3),
        "activity": round(activity, 3),
        "bus_factor": round(bus_factor, 3),
        "issue_resolution": round(issue_resolution, 3),
        "pr_merge": round(pr_merge, 3),
        "releases": round(releases, 3),
        "documentation": round(docs, 3),
        "dependency_freshness": round(deps, 3),
        "backlog_health": round(backlog, 3),
    }

    logger.debug("repository.quality", repo=repo.full_name, score=quality_score, label=label)
    assessment = RepositoryQualityAssessment(
        score=quality_score,
        label=label,
        insight=insight,
        factors=factors,
        clone_risk_warning=clone_risk,
    )
    return assessment


def build_repository_intelligence(
    repo: RepositoryItem,
    *,
    signals: RepositoryDeepSignals | None = None,
    intent: PersonalizationIntent | None = None,
    summary: RepositorySummary | None = None,
) -> RepositoryIntelligence:
    signals = signals or build_lightweight_signals(repo)
    quality = assess_repository_quality(repo, signals)
    fit = _fit_score(repo, signals, intent)
    trend_label, trend_note = _trend_label(repo, signals)
    maintenance_status = _maintenance_status(signals, quality.score, repo.archived)
    return RepositoryIntelligence(
        quality=quality,
        fit=fit,
        summary=summary,
        clone_risk_warning=quality.clone_risk_warning,
        trend_label=trend_label,
        trend_note=trend_note,
        maintenance_status=maintenance_status,
        documentation_quality=signals.documentation_quality,
        dependency_freshness=signals.dependency_freshness,
    )


def build_intent_from_search_request(request: SearchRequest) -> PersonalizationIntent | None:
    constraints = list(request.constraints or [])
    for key in (
        "beginner_friendly",
        "good_first_issues",
        "actively_maintained",
        "low_setup_complexity",
        "high_documentation_quality",
        "no_external_paid_apis",
        "trending_now",
    ):
        value = getattr(request, key, None)
        if value:
            constraints.append(key.replace("_", " "))
    if not any([request.experience_level, request.goal, constraints]):
        return None
    return PersonalizationIntent(
        experience_level=request.experience_level,
        goal=request.goal,
        constraints=constraints,
    )


def suggest_query_refinements(parsed: ParsedGitHubQuery, repos: list[RepositoryItem]) -> list[QueryRefinementSuggestion]:
    suggestions: list[QueryRefinementSuggestion] = []
    if not repos:
        suggestions.append(
            QueryRefinementSuggestion(
                message="No results returned",
                reason="The query may be too specific or GitHub rate limiting may be affecting coverage.",
                action="Try removing one filter or broadening the query terms.",
            )
        )
        return suggestions

    avg_score = sum(repo.score for repo in repos) / max(len(repos), 1)
    avg_recency = sum(_recency_score(repo.pushed_at) for repo in repos) / len(repos)
    avg_docs = sum((repo.intelligence.documentation_quality if repo.intelligence and repo.intelligence.documentation_quality is not None else build_lightweight_signals(repo).documentation_quality) for repo in repos) / len(repos)

    if avg_score < 0.35 and not parsed.min_stars:
        suggestions.append(
            QueryRefinementSuggestion(
                message="Results are broad and mixed quality",
                reason="The ranking spread suggests the query is still too general.",
                action="Add a programming language, topic, or minimum stars filter.",
            )
        )
    if avg_recency < 0.35 and not parsed.pushed_after:
        suggestions.append(
            QueryRefinementSuggestion(
                message="Many matches are outdated",
                reason="Recent activity is low across the first page of results.",
                action="Add a pushed-after filter such as a recent year.",
            )
        )
    if avg_docs < 0.45 and not parsed.high_documentation_quality:
        suggestions.append(
            QueryRefinementSuggestion(
                message="Documentation quality is uneven",
                reason="Several repositories appear light on onboarding material.",
                action="Add 'beginner-friendly' or 'documentation' to the query.",
            )
        )
    if parsed.goal == "learning" and not parsed.experience_level:
        suggestions.append(
            QueryRefinementSuggestion(
                message="Learning intent detected",
                reason="The query looks educational, but the desired difficulty is unclear.",
                action="Specify beginner, intermediate, or advanced to improve fit.",
            )
        )
    return suggestions[:3]
