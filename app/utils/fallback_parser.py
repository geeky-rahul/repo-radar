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
    tokens = re.findall(r"[a-z0-9#+]+", lower)

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

    # Build clean keyword query
    stop: set[str] = _FILLER_WORDS | set(_LANGUAGES) | set(_STAR_SIGNALS.keys()) | _RECENCY_SIGNALS
    keywords = [t for t in tokens if t not in stop and len(t) > 1]
    clean_query = " ".join(dict.fromkeys(keywords))  # deduplicate, preserve order

    return ParsedGitHubQuery(
        query=clean_query or user_query.strip(),
        language=detected_language,
        min_stars=min_stars,
        pushed_after=pushed_after,
    )
