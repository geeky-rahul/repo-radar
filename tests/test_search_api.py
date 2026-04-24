"""
Integration tests for the /api/v1/search/repositories endpoint.
GitHub API and LLM are mocked — no live network calls required.
Run with: pytest tests/test_search_api.py -v
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.main import app
from app.schemas.search import ParsedGitHubQuery, RepositoryItem


# ─── Fixtures ─────────────────────────────────────────────────────────────────

MOCK_PARSED_QUERY = ParsedGitHubQuery(
    query="python chatbot beginner",
    language="python",
    min_stars=100,
    pushed_after=None,
)

MOCK_REPOS = [
    RepositoryItem(
        id=i,
        name=f"repo-{i}",
        full_name=f"user/repo-{i}",
        html_url=f"https://github.com/user/repo-{i}",
        description="A cool chatbot project" if i % 2 == 0 else None,
        stargazers_count=1000 * i,
        forks_count=50 * i,
        open_issues_count=5,
        language="Python",
        pushed_at="2024-06-01T00:00:00Z",
        created_at="2023-01-01T00:00:00Z",
        topics=["chatbot", "python"],
        license_name="MIT",
        owner_login="user",
        owner_avatar_url=None,
        score=0.0,
    )
    for i in range(1, 6)
]


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_search_pipeline():
    """Patch both the LLM agent and GitHub tool."""
    with (
        patch("app.services.search.parse_query", new_callable=AsyncMock, return_value=MOCK_PARSED_QUERY),
        patch("app.services.search.search_github_repositories", new_callable=AsyncMock, return_value=MOCK_REPOS),
        patch("app.services.search.cache_get", new_callable=AsyncMock, return_value=None),
        patch("app.services.search.cache_set", new_callable=AsyncMock),
    ):
        yield


# ─── Tests ────────────────────────────────────────────────────────────────────

class TestSearchEndpoint:
    def test_successful_search(self, client, mock_search_pipeline):
        response = client.post(
            "/api/v1/search/repositories",
            json={"query": "best beginner python chatbot project"},
        )
        assert response.status_code == 200
        data = response.json()

        assert data["original_query"] == "best beginner python chatbot project"
        assert "parsed_query" in data
        assert "results" in data
        assert len(data["results"]) > 0
        assert data["cached"] is False
        assert data["duration_ms"] >= 0

    def test_results_have_required_fields(self, client, mock_search_pipeline):
        response = client.post(
            "/api/v1/search/repositories",
            json={"query": "python machine learning library"},
        )
        assert response.status_code == 200
        repo = response.json()["results"][0]

        required_fields = ["id", "name", "full_name", "html_url", "stargazers_count", "score"]
        for field in required_fields:
            assert field in repo, f"Missing field: {field}"

    def test_results_sorted_by_score(self, client, mock_search_pipeline):
        response = client.post(
            "/api/v1/search/repositories",
            json={"query": "popular rust web framework"},
        )
        results = response.json()["results"]
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_query_too_short_rejected(self, client):
        response = client.post(
            "/api/v1/search/repositories",
            json={"query": "ab"},
        )
        assert response.status_code == 422

    def test_query_too_long_rejected(self, client):
        response = client.post(
            "/api/v1/search/repositories",
            json={"query": "a" * 257},
        )
        assert response.status_code == 422

    def test_top_k_respected(self, client, mock_search_pipeline):
        response = client.post(
            "/api/v1/search/repositories",
            json={"query": "python data science", "top_k": 3},
        )
        assert response.status_code == 200
        assert len(response.json()["results"]) <= 3

    def test_language_override_applied(self, client, mock_search_pipeline):
        response = client.post(
            "/api/v1/search/repositories",
            json={"query": "web framework", "language": "rust", "min_stars": 200},
        )
        assert response.status_code == 200
        # Parsed query reflects the override
        assert response.json()["parsed_query"]["language"] == "rust"

    def test_advanced_qualifier_overrides_applied(self, client, mock_search_pipeline):
        response = client.post(
            "/api/v1/search/repositories",
            json={
                "query": "python service",
                "fork": False,
                "archived": True,
                "topic": "cli",
                "license": "MIT",
            },
        )
        assert response.status_code == 200
        parsed = response.json()["parsed_query"]
        assert parsed["fork"] is False
        assert parsed["archived"] is True
        assert parsed["topic"] == "cli"
        assert parsed["license"] == "MIT"

    def test_github_error_returns_502(self, client):
        from app.core.exceptions import GitHubAPIError

        with (
            patch("app.services.search.parse_query", new_callable=AsyncMock, return_value=MOCK_PARSED_QUERY),
            patch("app.services.search.search_github_repositories", new_callable=AsyncMock,
                  side_effect=GitHubAPIError("GitHub down")),
            patch("app.services.search.cache_get", new_callable=AsyncMock, return_value=None),
        ):
            response = client.post(
                "/api/v1/search/repositories",
                json={"query": "python chatbot"},
            )
        assert response.status_code == 502
        assert response.json()["detail"]["code"] == "GITHUB_API_ERROR"

    def test_rate_limit_returns_429(self, client):
        from app.core.exceptions import GitHubRateLimitError

        with (
            patch("app.services.search.parse_query", new_callable=AsyncMock, return_value=MOCK_PARSED_QUERY),
            patch("app.services.search.search_github_repositories", new_callable=AsyncMock,
                  side_effect=GitHubRateLimitError("Rate limited")),
            patch("app.services.search.cache_get", new_callable=AsyncMock, return_value=None),
        ):
            response = client.post(
                "/api/v1/search/repositories",
                json={"query": "python chatbot"},
            )
        assert response.status_code == 429

    def test_cached_response_flag(self, client):
        from app.services.search import SearchResponse
        cached_payload = {
            "original_query": "python chatbot",
            "parsed_query": MOCK_PARSED_QUERY.model_dump(),
            "total_found": 5,
            "results": [r.model_dump() for r in MOCK_REPOS[:3]],
            "cached": False,
            "duration_ms": 120.0,
        }
        with patch("app.services.search.cache_get", new_callable=AsyncMock, return_value=cached_payload):
            response = client.post(
                "/api/v1/search/repositories",
                json={"query": "python chatbot"},
            )
        assert response.status_code == 200
        assert response.json()["cached"] is True


class TestHealthEndpoint:
    def test_health_ok(self, client):
        with patch("app.api.v1.health.get_redis", new_callable=AsyncMock, return_value=None):
            response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["cache"] in ("ok", "unavailable")
