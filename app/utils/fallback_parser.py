"""
Rule-based fallback query parser.
Used when the LLM is unavailable or fails.
Provides deterministic extraction of language, stars, and recency signals.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from app.schemas.search import ParsedGitHubQuery

# Known programming languages (ordered longest-first to avoid partial matches)
_LANGUAGES: list[str] = [
    "typescript", "javascript", "python", "rust", "golang", "go", "java",
    "kotlin", "swift", "c++", "cpp", "c#", "csharp", "ruby", "php",
    "scala", "haskell", "elixir", "dart", "julia", "r",
]

_FILLER_WORDS: set[str] = {
    "project", "projects", "repo", "repos", "repository", "repositories",
    "a", "an", "the", "for", "with", "and", "or", "some", "any",
    "me", "my", "find", "search", "show", "give", "i", "want",
    "need", "looking", "look", "get", "fetch",
}

_STAR_SIGNALS: dict[str, int] = {
    "popular": 1000,
    "trending": 500,
    "best": 500,
    "top": 500,
    "beginner": 100,
    "simple": 50,
    "minimal": 50,
}

_RECENCY_SIGNALS: set[str] = {
    "recent", "new", "latest", "updated", "modern", "fresh", "2024", "2025",
}


def fallback_parse_query(user_query: str) -> ParsedGitHubQuery:
    lower = user_query.lower()
    qualifier_cleaned = re.sub(
        r"\b(topic|license)\s*:\s*[a-z0-9_.-]+\b",
        "",
        lower,
    )
    qualifier_cleaned = re.sub(
        r"\b(fork|archived)\s*:\s*(true|false)\b",
        "",
        qualifier_cleaned,
    )
    tokens = re.findall(r"[a-z0-9#+]+", qualifier_cleaned)

    # Detect language — use word-boundary matching to avoid false positives
    # e.g. "r" should not match "library" or "react"
    detected_language: str | None = None
    for lang in _LANGUAGES:
        # Build a safe pattern; escape special regex chars (e.g. c++, c#)
        escaped = re.escape(lang)
        if re.search(rf"(?<![a-z0-9#]){escaped}(?![a-z0-9#])", lower):
            detected_language = lang if lang not in ("cpp", "csharp", "golang") else {
                "cpp": "c++", "csharp": "c#", "golang": "go"
            }[lang]
            break

    # Infer min_stars
    min_stars = 0
    for signal, stars in _STAR_SIGNALS.items():
        if signal in lower:
            min_stars = max(min_stars, stars)

    # Detect recency
    pushed_after: str | None = None
    for signal in _RECENCY_SIGNALS:
        if signal in lower:
            year = datetime.now(tz=timezone.utc).year
            pushed_after = f"{year}-01-01"
            break

    # Detect explicit qualifiers
    fork: bool | None = None
    archived: bool | None = None
    topic: str | None = None
    license_value: str | None = None

    fork_match = re.search(r"fork\s*:\s*(true|false)", lower)
    if fork_match:
        fork = fork_match.group(1) == "true"
    elif "exclude forks" in lower or "no forks" in lower:
        fork = False
    elif "include forks" in lower or "forked repos" in lower:
        fork = True

    archived_match = re.search(r"archived\s*:\s*(true|false)", lower)
    if archived_match:
        archived = archived_match.group(1) == "true"
    elif "exclude archived" in lower or "not archived" in lower:
        archived = False
    elif "archived repos" in lower or "archived" in lower:
        archived = True

    topic_match = re.search(r"topic\s*:\s*([a-z0-9_.-]+)", lower)
    if topic_match:
        topic = topic_match.group(1)

    license_match = re.search(r"license\s*:\s*([a-z0-9+.-]+)", lower)
    if license_match:
        license_value = license_match.group(1).upper()

    # Build clean keyword query
    stop: set[str] = _FILLER_WORDS | set(_LANGUAGES) | set(_STAR_SIGNALS.keys()) | _RECENCY_SIGNALS
    keywords = [t for t in tokens if t not in stop and len(t) > 1]
    clean_query = " ".join(dict.fromkeys(keywords))  # deduplicate, preserve order

    return ParsedGitHubQuery(
        query=clean_query or user_query.strip(),
        language=detected_language,
        min_stars=min_stars,
        pushed_after=pushed_after,
        fork=fork,
        archived=archived,
        topic=topic,
        license=license_value,
    )
