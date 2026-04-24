"""
Unit tests for the repository ranking service.
Run with: pytest tests/test_ranking.py -v
"""
from __future__ import annotations

import pytest

from app.schemas.search import RepositoryItem
from app.services.ranking import (
    _stars_score,
    _recency_score,
    _completeness_score,
    _contributor_activity_score,
    _community_health_score,
    _trend_score,
    rank_repositories,
)


def _make_repo(**kwargs) -> RepositoryItem:
    defaults = dict(
        id=1,
        name="test-repo",
        full_name="user/test-repo",
        html_url="https://github.com/user/test-repo",
        description=None,
        stargazers_count=0,
        forks_count=0,
        open_issues_count=0,
        language=None,
        pushed_at=None,
        created_at=None,
        topics=[],
        license_name=None,
        owner_login="user",
        owner_avatar_url=None,
        score=0.0,
    )
    defaults.update(kwargs)
    return RepositoryItem(**defaults)


class TestStarsScore:
    def test_zero_stars(self):
        assert _stars_score(0) == 0.0

    def test_one_star(self):
        assert 0 < _stars_score(1) < 0.1

    def test_many_stars(self):
        assert _stars_score(100_000) > _stars_score(1_000)

    def test_capped(self):
        assert _stars_score(999_999) == _stars_score(200_000)

    def test_bounded(self):
        for n in [1, 100, 1000, 10_000, 200_000]:
            assert 0.0 <= _stars_score(n) <= 1.0


class TestRecencyScore:
    def test_none(self):
        assert _recency_score(None) == 0.0

    def test_today(self):
        from datetime import datetime, timezone
        today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        assert _recency_score(today) > 0.99

    def test_old_repo(self):
        assert _recency_score("2015-01-01T00:00:00Z") < 0.1

    def test_invalid(self):
        assert _recency_score("not-a-date") == 0.0


class TestCompletenessScore:
    def test_empty_repo(self):
        repo = _make_repo()
        assert _completeness_score(repo) == 0.1

    def test_full_metadata(self):
        repo = _make_repo(
            description="A very useful library for doing things",
            topics=["python", "library"],
            license_name="MIT",
            language="Python",
        )
        score = _completeness_score(repo)
        assert score == 1.0

    def test_only_description(self):
        repo = _make_repo(description="Short desc here for testing purposes")
        assert _completeness_score(repo) == 0.55


class TestContributorActivityScore:
    def test_recent_repo_with_forks_scored_high(self):
        from datetime import datetime, timezone

        today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        repo = _make_repo(pushed_at=today, forks_count=500)

        score = _contributor_activity_score(repo)

        assert 0.0 < score <= 1.0
        assert score > 0.3

    def test_archived_repo_has_no_activity(self):
        repo = _make_repo(archived=True, pushed_at="2024-01-01T00:00:00Z", forks_count=1000)
        assert _contributor_activity_score(repo) == 0.0


class TestCommunityHealthScore:
    def test_low_open_issues_and_ci_have_good_health(self):
        repo = _make_repo(open_issues_count=5, topics=["github-actions", "python"])
        score = _community_health_score(repo)

        assert 0.5 < score <= 1.0

    def test_many_open_issues_penalized(self):
        repo = _make_repo(open_issues_count=200)
        assert _community_health_score(repo) < 0.5

    def test_archived_repo_has_no_health(self):
        repo = _make_repo(archived=True, open_issues_count=0, topics=["ci"])
        assert _community_health_score(repo) == 0.0


class TestTrendScore:
    def test_new_repo_with_stars_is_trending(self):
        from datetime import datetime, timezone, timedelta

        created = (datetime.now(tz=timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        repo = _make_repo(created_at=created, stargazers_count=300)

        assert _trend_score(repo) > 0.0

    def test_old_repo_has_lower_trend(self):
        repo = _make_repo(created_at="2010-01-01T00:00:00Z", stargazers_count=1000)
        assert _trend_score(repo) < 0.2


class TestRankRepositories:
    def test_empty_list(self):
        assert rank_repositories([]) == []

    def test_higher_stars_ranks_higher(self):
        low = _make_repo(id=1, stargazers_count=100)
        high = _make_repo(id=2, stargazers_count=50_000)
        ranked = rank_repositories([low, high])
        assert ranked[0].id == 2

    def test_scores_attached(self):
        repos = [_make_repo(stargazers_count=1000)]
        ranked = rank_repositories(repos)
        assert ranked[0].score > 0.0

    def test_sorted_descending(self):
        repos = [
            _make_repo(id=i, stargazers_count=i * 100)
            for i in range(5)
        ]
        ranked = rank_repositories(repos)
        scores = [r.score for r in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_original_list_unmodified(self):
        repos = [_make_repo(stargazers_count=500)]
        original_score = repos[0].score
        rank_repositories(repos)
        assert repos[0].score == original_score
