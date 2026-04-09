"""
Unit tests for the rule-based fallback query parser.
Run with: pytest tests/test_fallback_parser.py -v
"""
from __future__ import annotations

import pytest

from app.utils.fallback_parser import fallback_parse_query


@pytest.mark.parametrize(
    "user_query, expected_language, expected_min_stars_gte, has_pushed_after",
    [
        ("best python chatbot project", "python", 500, False),
        ("popular rust web framework", "rust", 1000, False),
        ("beginner javascript todo app", "javascript", 100, False),
        ("recent golang microservices", "go", 0, True),
        ("simple react dashboard", None, 50, False),
        ("trending typescript orm", "typescript", 500, False),
        ("latest machine learning library", None, 0, True),
        ("c++ game engine", "c++", 0, False),
    ],
)
def test_fallback_parse_query(
    user_query: str,
    expected_language: str | None,
    expected_min_stars_gte: int,
    has_pushed_after: bool,
) -> None:
    result = fallback_parse_query(user_query)
    assert result.language == expected_language
    assert result.min_stars >= expected_min_stars_gte
    assert bool(result.pushed_after) == has_pushed_after
    assert len(result.query) > 0


def test_fallback_produces_clean_query() -> None:
    result = fallback_parse_query("find me the best python machine learning projects")
    # filler words removed
    assert "find" not in result.query
    assert "me" not in result.query
    assert "the" not in result.query


def test_fallback_handles_minimal_input() -> None:
    result = fallback_parse_query("api")
    assert result.query  # should not be empty
    assert result.min_stars == 0
    assert result.language is None
