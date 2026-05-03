"""Repository deep summary and starter guide generation."""
from __future__ import annotations

from typing import Any

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.intelligence import RepositoryDeepSignals, RepositorySummary, StarterGuide
from app.services.cache import cache_get, cache_set
from app.tools.github_repository import fetch_repository_bundle, heuristics_from_bundle

logger = get_logger(__name__)
_CACHE_NAMESPACE = "repository_analysis_v1"

_SUMMARY_PROMPT = """\
You are a senior repository analyst.
Summarize the repository using the bundle of GitHub metadata, file tree, README text, and dependency hints.
Return structured output only.

Rules:
- What it does should be concise and accurate.
- How it works should describe the architecture at a high level.
- Key files should be the most useful starting files.
- Complexity should be one of Beginner, Intermediate, or Advanced.
- First things to try should be practical onboarding actions.
- Common issues should focus on setup and dependency problems.

{format_instructions}
"""


def _derive_summary_from_bundle(bundle: dict[str, Any], signals: RepositoryDeepSignals) -> RepositorySummary:
    repo = bundle.get("repository", {})
    full_name = repo.get("full_name", "this repository")
    architecture = signals.architecture_pattern
    complexity = signals.summary or "Intermediate"

    if architecture == "microservices":
        how_it_works = "The project is split across multiple service boundaries with clearly separated responsibilities."
    elif architecture == "modular":
        how_it_works = "The project is organized into modules and feature-oriented folders around a main application entry point."
    elif architecture == "library":
        how_it_works = "The repository behaves like a reusable library or toolkit with a small set of public entry points."
    else:
        how_it_works = "The repository uses a straightforward application structure centered around one or more entry files."

    if signals.readme_word_count < 250:
        what_it_does = f"{full_name} is a codebase that appears to solve a focused developer problem, but the README is light on onboarding detail."
    else:
        what_it_does = f"{full_name} provides a focused developer workflow or product experience, with repository structure reinforcing its purpose."

    setup_steps = [
        "Clone the repository and open the project root.",
        "Install the dependencies from the primary package file.",
        "Create any required environment variables from the sample config.",
        "Run the documented start command and verify the main entry point."
    ]

    common_issues = []
    if any(path.endswith("requirements.txt") for path in signals.key_files):
        common_issues.append("Python dependency mismatches if the virtual environment is not activated.")
    if any(path.endswith("package.json") for path in signals.key_files):
        common_issues.append("Node package installs may fail if the lockfile and package manager versions are out of sync.")
    if not signals.has_readme:
        common_issues.append("Missing or thin documentation makes initial setup harder.")
    if not common_issues:
        common_issues.append("Environment variables and platform-specific commands are the most common onboarding issues.")

    first_things = [
        "Open the main entry point and locate the request or startup path.",
        "Inspect the configuration layer for environment variables and external services.",
        "Run the app locally and verify the core happy path before exploring advanced features.",
    ]

    return RepositorySummary(
        what_it_does=what_it_does,
        how_it_works=how_it_works,
        key_files=signals.key_files[:5],
        complexity=signals.summary or complexity,
        primary_languages=bundle.get("primary_languages", []),
        architecture_pattern=architecture,
        entry_points=signals.entry_points,
        core_modules=signals.core_modules,
        setup_steps=setup_steps,
        first_things_to_try=first_things,
        common_issues=common_issues,
    )


def _derive_signals_from_bundle(bundle: dict[str, Any]) -> RepositoryDeepSignals:
    heuristic = heuristics_from_bundle(bundle)
    return RepositoryDeepSignals(
        recent_commits_30d=bundle.get("recent_commits_30d", 0),
        recent_commits_90d=bundle.get("recent_commits_90d", 0),
        contributor_count=bundle.get("contributor_count", 0),
        issue_resolution_rate=bundle.get("issue_resolution_rate"),
        pr_merge_rate=bundle.get("pr_merge_rate"),
        release_frequency_per_month=bundle.get("release_frequency_per_month", 0.0),
        documentation_quality=heuristic["documentation_quality"],
        dependency_freshness=heuristic["dependency_freshness"],
        open_issue_backlog_ratio=bundle.get("open_issue_backlog_ratio", 0.0),
        has_readme=bool(bundle.get("readme")),
        readme_word_count=heuristic["readme_word_count"],
        primary_language_count=len(bundle.get("primary_languages", [])),
        architecture_pattern=heuristic["architecture"],
        entry_points=heuristic["entry_points"],
        key_files=heuristic["key_files"],
        core_modules=heuristic["core_modules"],
        summary=heuristic["complexity_label"],
    )


async def analyze_repository(full_name: str) -> tuple[dict[str, Any], RepositoryDeepSignals, RepositorySummary]:
    cached = await cache_get(_CACHE_NAMESPACE, {"full_name": full_name})
    if cached:
        return (
            cached["bundle"],
            RepositoryDeepSignals.model_validate(cached["signals"]),
            RepositorySummary.model_validate(cached["summary"]),
        )

    bundle = await fetch_repository_bundle(full_name)
    signals = _derive_signals_from_bundle(bundle)
    summary = _derive_summary_from_bundle(bundle, signals)
    await cache_set(
        _CACHE_NAMESPACE,
        {"full_name": full_name},
        {
            "bundle": bundle,
            "signals": signals.model_dump(),
            "summary": summary.model_dump(),
        },
    )
    return bundle, signals, summary


def build_starter_guide(full_name: str, bundle: dict[str, Any], summary: RepositorySummary, signals: RepositoryDeepSignals) -> StarterGuide:
    repo = bundle.get("repository", {})
    files = bundle.get("files", [])
    install_dependencies: list[str] = []
    run_commands: list[str] = []
    environment_setup: list[str] = []
    notes: list[str] = []

    if any(path.endswith("requirements.txt") for path in files):
        install_dependencies.append("python -m pip install -r requirements.txt")
    if any(path.endswith("pyproject.toml") for path in files):
        install_dependencies.append("python -m pip install .")
    if any(path.endswith("package.json") for path in files):
        install_dependencies.append("npm install")
    if any(path.endswith("Dockerfile") for path in files):
        install_dependencies.append("docker build -t repo .")
    if not install_dependencies:
        install_dependencies.append("Inspect the primary package file and install the documented dependencies.")

    if repo.get("language") == "Python":
        environment_setup.append("Create and activate a virtual environment before installing packages.")
        run_commands.append("python -m uvicorn app.main:app --reload")
    elif repo.get("language") in {"JavaScript", "TypeScript"}:
        environment_setup.append("Use the project’s package manager and check for a .env.example file.")
        run_commands.append("npm run dev")
    else:
        environment_setup.append("Check the README for the canonical runtime and command sequence.")

    if summary.entry_points:
        notes.append(f"Primary entry points: {', '.join(summary.entry_points[:3])}")
    if signals.documentation_quality < 0.45:
        notes.append("Documentation is thin, so onboarding may require more manual exploration.")

    return StarterGuide(
        repository=full_name,
        install_dependencies=install_dependencies,
        environment_setup=environment_setup,
        run_commands=run_commands,
        common_issues=summary.common_issues,
        first_things_to_try=summary.first_things_to_try,
        notes=notes,
    )
