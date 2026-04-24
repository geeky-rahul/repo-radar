"""Unit tests for GitHub query builder and fallback qualifier parsing."""
from __future__ import annotations

from app.schemas.search import ParsedGitHubQuery
from app.tools.github_search import _build_github_query
from app.utils.fallback_parser import fallback_parse_query


def test_build_github_query_includes_advanced_qualifiers() -> None:
    parsed = ParsedGitHubQuery(
        query="python cli tool",
        language="python",
        min_stars=200,
        pushed_after="2025-01-01",
        fork=False,
        archived=True,
        topic="cli",
        license="MIT",
    )

    github_query = _build_github_query(parsed)

    assert "python cli tool" in github_query
    assert "language:python" in github_query
    assert "stars:>=200" in github_query
    assert "pushed:>=2025-01-01" in github_query
    assert "fork:false" in github_query
    assert "archived:true" in github_query
    assert "topic:cli" in github_query
    assert "license:MIT" in github_query


def test_fallback_parser_extracts_explicit_qualifiers() -> None:
    query = "best python repo topic:cli license:MIT fork:false archived:true"
    parsed = fallback_parse_query(query)

    assert parsed.topic == "cli"
    assert parsed.license == "MIT"
    assert parsed.fork is False
    assert parsed.archived is True
    assert parsed.query.startswith("best python repo")
