"""Repository intelligence endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.core.exceptions import GitHubAPIError
from app.core.logging import get_logger
from app.schemas.intelligence import (
    ComparisonRequest,
    ComparisonResponse,
    RepositoryAnalysisResponse,
    RepositorySummary,
    StarterGuide,
)
from app.schemas.search import RepositoryItem
from app.services.comparison_service import compare_repositories
from app.services.scoring_service import build_repository_intelligence
from app.services.summarization_service import analyze_repository, build_starter_guide

router = APIRouter(prefix="/intelligence", tags=["intelligence"])
logger = get_logger(__name__)


def _repo_from_bundle(bundle: dict) -> RepositoryItem:
    repo = bundle.get("repository", {})
    owner = repo.get("owner", {})
    license_info = repo.get("license") or {}
    return RepositoryItem(
        id=repo["id"],
        name=repo["name"],
        full_name=repo["full_name"],
        html_url=repo["html_url"],
        description=repo.get("description"),
        stargazers_count=repo.get("stargazers_count", 0),
        forks_count=repo.get("forks_count", 0),
        open_issues_count=repo.get("open_issues_count", 0),
        language=repo.get("language"),
        pushed_at=repo.get("pushed_at"),
        created_at=repo.get("created_at"),
        topics=repo.get("topics", []),
        license_name=license_info.get("name"),
        archived=repo.get("archived", False),
        owner_login=owner.get("login", ""),
        owner_avatar_url=owner.get("avatar_url"),
    )


@router.get("/repositories/{owner}/{repo}/analysis", response_model=RepositoryAnalysisResponse, summary="Analyze a repository")
async def analyze_repository_endpoint(owner: str, repo: str) -> RepositoryAnalysisResponse:
    full_name = f"{owner}/{repo}"
    try:
        bundle, signals, summary = await analyze_repository(full_name)
        repo_item = _repo_from_bundle(bundle)
        intelligence = build_repository_intelligence(repo_item, signals=signals, summary=summary)
        return RepositoryAnalysisResponse(repository=full_name, intelligence=intelligence, source_url=repo_item.html_url)
    except GitHubAPIError as exc:
        logger.warning("repo_analysis.github_error", repo=full_name, error=exc.message)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.message) from exc


@router.get("/repositories/{owner}/{repo}/summary", response_model=RepositorySummary, summary="Get a deep repository summary")
async def repository_summary_endpoint(owner: str, repo: str) -> RepositorySummary:
    full_name = f"{owner}/{repo}"
    try:
        _, _, summary = await analyze_repository(full_name)
        return summary
    except GitHubAPIError as exc:
        logger.warning("repo_summary.github_error", repo=full_name, error=exc.message)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.message) from exc


@router.get("/repositories/{owner}/{repo}/starter", response_model=StarterGuide, summary="Get a starter guide")
async def repository_starter_endpoint(owner: str, repo: str) -> StarterGuide:
    full_name = f"{owner}/{repo}"
    try:
        bundle, signals, summary = await analyze_repository(full_name)
        return build_starter_guide(full_name, bundle, summary, signals)
    except GitHubAPIError as exc:
        logger.warning("repo_starter.github_error", repo=full_name, error=exc.message)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.message) from exc


@router.post("/compare", response_model=ComparisonResponse, summary="Compare 2-5 repositories")
async def compare_repositories_endpoint(request: ComparisonRequest) -> ComparisonResponse:
    try:
        return await compare_repositories(request)
    except GitHubAPIError as exc:
        logger.warning("repo_compare.github_error", error=exc.message)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.message) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
