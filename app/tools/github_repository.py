"""GitHub repository introspection helpers."""
from __future__ import annotations

from collections import Counter
import asyncio
from typing import Any
import re

import httpx

from app.core.config import get_settings
from app.core.exceptions import GitHubAPIError
from app.core.logging import get_logger

logger = get_logger(__name__)


def _headers(extra_accept: str | None = None) -> dict[str, str]:
    settings = get_settings()
    headers: dict[str, str] = {
        "Accept": extra_accept or "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    return headers


async def _get_json(client: httpx.AsyncClient, url: str, *, params: dict[str, Any] | None = None, accept: str | None = None) -> tuple[Any, httpx.Response]:
    response = await client.get(url, headers=_headers(accept), params=params)
    if response.status_code == 404:
        raise GitHubAPIError("GitHub repository resource was not found", {"url": url})
    if response.status_code != 200:
        raise GitHubAPIError(
            f"GitHub API returned {response.status_code}",
            {"url": url, "body": response.text[:500]},
        )
    return response.json(), response


async def _get_text(client: httpx.AsyncClient, url: str) -> str | None:
    response = await client.get(url, headers=_headers("application/vnd.github.raw"))
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise GitHubAPIError(
            f"GitHub API returned {response.status_code}",
            {"url": url, "body": response.text[:500]},
        )
    return response.text


def _normalize_repo_name(full_name: str) -> str:
    owner, repo = full_name.split("/", 1)
    return f"{owner.strip()}/{repo.strip()}"


def _content_preview(text: str | None, limit: int = 4000) -> str | None:
    if not text:
        return None
    cleaned = re.sub(r"\r\n", "\n", text)
    return cleaned[:limit]


async def fetch_repository_bundle(full_name: str) -> dict[str, Any]:
    full_name = _normalize_repo_name(full_name)
    settings = get_settings()
    base_url = settings.github_api_base_url.rstrip("/")
    repo_url = f"{base_url}/repos/{full_name}"

    async with httpx.AsyncClient(timeout=settings.github_request_timeout) as client:
        repo_data, _ = await _get_json(client, repo_url)
        default_branch = repo_data.get("default_branch") or "main"

        (
            tree_data,
            languages_data,
            readme_text,
            contributors_data,
            commits_30_data,
            commits_90_data,
            releases_data,
            open_issues_data,
            closed_issues_data,
            merged_prs_data,
            closed_prs_data,
        ) = await asyncio.gather(
            _get_json(client, f"{repo_url}/git/trees/{default_branch}", params={"recursive": 1}),
            _get_json(client, f"{repo_url}/languages"),
            _get_text(client, f"{repo_url}/readme"),
            _get_json(client, f"{repo_url}/contributors", params={"per_page": 100, "anon": 1}),
            _get_json(client, f"{repo_url}/commits", params={"since": _iso_days_ago(30), "per_page": 100}),
            _get_json(client, f"{repo_url}/commits", params={"since": _iso_days_ago(90), "per_page": 100}),
            _get_json(client, f"{repo_url}/releases", params={"per_page": 100}),
            _get_json(client, f"{base_url}/search/issues", params={"q": f"repo:{full_name} is:issue is:open", "per_page": 1}),
            _get_json(client, f"{base_url}/search/issues", params={"q": f"repo:{full_name} is:issue is:closed", "per_page": 1}),
            _get_json(client, f"{base_url}/search/issues", params={"q": f"repo:{full_name} is:pr is:merged", "per_page": 1}),
            _get_json(client, f"{base_url}/search/issues", params={"q": f"repo:{full_name} is:pr is:closed", "per_page": 1}),
        )

    tree_payload = tree_data[0] if isinstance(tree_data, tuple) else tree_data
    tree_items = tree_payload.get("tree", []) if isinstance(tree_payload, dict) else []
    file_paths = count_tree_files(tree_items)
    contributors = contributors_data[0] if isinstance(contributors_data, tuple) else contributors_data
    releases = releases_data[0] if isinstance(releases_data, tuple) else releases_data
    open_issues = open_issues_data[0] if isinstance(open_issues_data, tuple) else open_issues_data
    closed_issues = closed_issues_data[0] if isinstance(closed_issues_data, tuple) else closed_issues_data
    merged_prs = merged_prs_data[0] if isinstance(merged_prs_data, tuple) else merged_prs_data
    closed_prs = closed_prs_data[0] if isinstance(closed_prs_data, tuple) else closed_prs_data
    commits_30 = commits_30_data[0] if isinstance(commits_30_data, tuple) else commits_30_data
    commits_90 = commits_90_data[0] if isinstance(commits_90_data, tuple) else commits_90_data
    languages = languages_data[0] if isinstance(languages_data, tuple) else languages_data

    contributor_count = len(contributors) if isinstance(contributors, list) else 0
    release_count = len(releases) if isinstance(releases, list) else 0
    commit_30_count = len(commits_30) if isinstance(commits_30, list) else 0
    commit_90_count = len(commits_90) if isinstance(commits_90, list) else 0
    open_issue_count = int(open_issues.get("total_count", repo_data.get("open_issues_count", 0))) if isinstance(open_issues, dict) else repo_data.get("open_issues_count", 0)
    closed_issue_count = int(closed_issues.get("total_count", 0)) if isinstance(closed_issues, dict) else 0
    merged_pr_count = int(merged_prs.get("total_count", 0)) if isinstance(merged_prs, dict) else 0
    closed_pr_count = int(closed_prs.get("total_count", 0)) if isinstance(closed_prs, dict) else 0

    issue_resolution_rate = closed_issue_count / max(closed_issue_count + open_issue_count, 1)
    pr_merge_rate = merged_pr_count / max(closed_pr_count, 1)
    release_frequency_per_month = release_count / max((commit_90_count / 30.0) or 1.0, 1.0)
    open_issue_backlog_ratio = open_issue_count / max(open_issue_count + closed_issue_count, 1)

    package_files = detect_package_files(file_paths)

    return {
        "repository": repo_data,
        "tree": tree_items,
        "files": file_paths,
        "languages": languages if isinstance(languages, dict) else {},
        "readme": _content_preview(readme_text),
        "contributor_count": contributor_count,
        "recent_commits_30d": commit_30_count,
        "recent_commits_90d": commit_90_count,
        "issue_resolution_rate": issue_resolution_rate,
        "pr_merge_rate": pr_merge_rate,
        "release_frequency_per_month": release_frequency_per_month,
        "open_issue_backlog_ratio": open_issue_backlog_ratio,
        "package_files": package_files,
        "primary_languages": list(languages.keys())[:3] if isinstance(languages, dict) else [],
    }


def _iso_days_ago(days: int) -> str:
    from datetime import datetime, timedelta, timezone

    return (datetime.now(tz=timezone.utc) - timedelta(days=days)).isoformat()


def count_tree_files(tree: list[dict[str, Any]]) -> list[str]:
    return [item.get("path", "") for item in tree if item.get("type") == "blob"]


def detect_entry_points(paths: list[str]) -> list[str]:
    entry_patterns = (
        "main.py",
        "app.py",
        "server.py",
        "index.js",
        "index.ts",
        "main.ts",
        "main.tsx",
        "app.ts",
        "app.tsx",
        "src/main.py",
        "src/main.js",
        "src/main.ts",
        "src/index.js",
        "src/index.ts",
    )
    return [path for path in paths if any(path.endswith(pattern) for pattern in entry_patterns)]


def detect_package_files(paths: list[str]) -> list[str]:
    package_candidates = {
        "requirements.txt",
        "pyproject.toml",
        "setup.py",
        "package.json",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
    }
    return [path for path in paths if path.split("/")[-1] in package_candidates]


def detect_architecture(paths: list[str]) -> str:
    lower_paths = [path.lower() for path in paths]
    folder_counts = Counter(path.split("/")[0] for path in lower_paths if "/" in path)
    if any(path.startswith(("services/", "apps/", "modules/", "microservices/")) for path in lower_paths) or len(folder_counts) >= 4:
        return "microservices" if any(path.startswith("services/") for path in lower_paths) else "modular"
    if any(path.startswith(("src/", "app/", "lib/")) for path in lower_paths):
        return "modular"
    return "library" if any(path.endswith((".py", ".js", ".ts", ".tsx")) for path in lower_paths) else "monolith"


def infer_complexity(file_count: int, architecture: str, entry_points: list[str], readme_word_count: int) -> str:
    score = 0
    if file_count > 250:
        score += 2
    elif file_count > 90:
        score += 1
    if architecture in {"microservices", "modular"}:
        score += 1
    if len(entry_points) > 1:
        score += 1
    if readme_word_count < 500:
        score += 1
    if score <= 1:
        return "Beginner"
    if score <= 3:
        return "Intermediate"
    return "Advanced"


def heuristics_from_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    repo = bundle.get("repository", {})
    tree = bundle.get("tree", [])
    paths = count_tree_files(tree)
    readme = bundle.get("readme") or ""
    language_items = bundle.get("languages", {})

    entry_points = detect_entry_points(paths)
    package_files = detect_package_files(paths)
    architecture = detect_architecture(paths)
    readme_word_count = len(re.findall(r"\b\w+\b", readme))
    complexity = infer_complexity(len(paths), architecture, entry_points, readme_word_count)

    docs_score = min(1.0, (0.25 if readme else 0.0) + min(readme_word_count / 1200.0, 0.45) + (0.15 if any(h in readme.lower() for h in ("install", "usage", "quick start", "getting started")) else 0.0) + (0.15 if "```" in readme else 0.0))
    lockfile_score = 0.0
    if any(path.endswith(("package-lock.json", "yarn.lock", "pnpm-lock.yaml")) for path in paths):
        lockfile_score = 0.85
    elif any(path.endswith("package.json") for path in paths):
        lockfile_score = 0.55
    elif any(path.endswith(("requirements.txt", "pyproject.toml", "setup.py")) for path in paths):
        lockfile_score = 0.65

    dependency_freshness = min(1.0, lockfile_score)
    primary_languages = list(language_items.keys())[:3] if isinstance(language_items, dict) else []

    return {
        "architecture": architecture,
        "complexity": complexity,
        "entry_points": entry_points,
        "key_files": package_files[:5] or [path for path in paths if path.endswith(("README.md", "README.rst", "README"))][:3],
        "core_modules": [path for path in paths if path.startswith(("src/", "app/", "lib/", "services/", "modules/"))][:8],
        "primary_languages": primary_languages,
        "readme_word_count": readme_word_count,
        "documentation_quality": docs_score,
        "dependency_freshness": dependency_freshness,
        "file_count": len(paths),
        "complexity_label": complexity,
    }
