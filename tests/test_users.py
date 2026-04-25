"""Integration tests for user account and personalization endpoints."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.search import RepositoryItem
from app.schemas.user import UserProfile, SavedSearchItem
from app.core.auth import get_current_user


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_user_profile():
    return UserProfile(
        user_id="google:123456789",
        email="test@example.com",
        name="Test User",
        avatar_url="https://example.com/avatar.jpg",
        github_username="testuser",
    )


@pytest.fixture
def mock_repo():
    return RepositoryItem(
        id=12345,
        name="test-repo",
        full_name="testuser/test-repo",
        html_url="https://github.com/testuser/test-repo",
        description="A test repository",
        stargazers_count=100,
        forks_count=20,
        open_issues_count=5,
        language="Python",
        pushed_at="2024-01-01T00:00:00Z",
        created_at="2023-01-01T00:00:00Z",
        topics=["python", "test"],
        license_name="MIT",
        archived=False,
        owner_login="testuser",
        owner_avatar_url=None,
        score=0.8,
    )


@pytest.fixture
def mock_saved_search():
    return SavedSearchItem(
        id="search123",
        name="My Search",
        query="python machine learning",
    )


class TestUserAuth:
    def test_google_login_success(self, client, monkeypatch):
        monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "fake_client_id")
        from app.core.config import get_settings
        get_settings.cache_clear()  # Clear the lru_cache
        
        with (
            patch("google.oauth2.id_token.verify_oauth2_token") as mock_verify,
            patch("app.api.v1.users.get_github_user_info", new_callable=AsyncMock) as mock_github,
            patch("app.api.v1.users.create_or_update_user_profile", new_callable=AsyncMock) as mock_create,
            patch("app.api.v1.users.create_session_for_user", new_callable=AsyncMock) as mock_session,
        ):
            mock_verify.return_value = {
                "sub": "123456789",
                "email": "test@example.com",
                "name": "Test User",
                "picture": "https://example.com/avatar.jpg",
            }
            mock_github.return_value = {"login": "testuser"}
            mock_session.return_value = "session_token_123"

            response = client.post(
                "/api/v1/users/auth/google",
                json={"id_token": "fake_token", "github_token": "fake_github_token"},
            )

            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert data["user"]["email"] == "test@example.com"
            assert data["user"]["github_username"] == "testuser"

    def test_google_login_invalid_token(self, client, monkeypatch):
        monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "fake_client_id")
        from app.core.config import get_settings
        get_settings.cache_clear()
        
        with patch("google.oauth2.id_token.verify_oauth2_token", side_effect=Exception("Invalid token")):
            response = client.post(
                "/api/v1/users/auth/google",
                json={"id_token": "invalid_token"},
            )
            assert response.status_code == 401

    def test_google_login_missing_client_id(self, client, monkeypatch):
        monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_ID", raising=False)
        from app.core.config import get_settings
        get_settings.cache_clear()
        
        response = client.post(
            "/api/v1/users/auth/google",
            json={"id_token": "fake_token"},
        )
        assert response.status_code == 500


class TestUserProfile:
    def test_get_current_profile_success(self, client, mock_user_profile):
        async def mock_get_current_user():
            return mock_user_profile
        
        app.dependency_overrides[get_current_user] = mock_get_current_user
        
        try:
            response = client.get(
                "/api/v1/users/me",
                headers={"Authorization": "Bearer fake_token"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == "google:123456789"
            assert data["email"] == "test@example.com"
        finally:
            app.dependency_overrides = {}

    def test_get_current_profile_unauthorized(self, client):
        response = client.get("/api/v1/users/me")
        assert response.status_code == 401


class TestFavorites:
    def test_get_favorites_success(self, client, mock_repo):
        mock_user = UserProfile(
            user_id="google:123456789",
            email="test@example.com",
            name="Test User",
            avatar_url="https://example.com/avatar.jpg",
            github_username="testuser",
        )
        
        async def mock_get_current_user():
            return mock_user
        
        app.dependency_overrides[get_current_user] = mock_get_current_user
        
        try:
            with patch("app.api.v1.users.list_favorite_repos", new_callable=AsyncMock) as mock_list:
                mock_list.return_value = [mock_repo]

                response = client.get(
                    "/api/v1/users/favorites",
                    headers={"Authorization": "Bearer fake_token"},
                )

                assert response.status_code == 200
                data = response.json()
                assert len(data) == 1
                assert data[0]["id"] == 12345
        finally:
            app.dependency_overrides = {}

    def test_add_favorite_success(self, client, mock_repo):
        mock_user = UserProfile(
            user_id="google:123456789",
            email="test@example.com",
            name="Test User",
            avatar_url="https://example.com/avatar.jpg",
            github_username="testuser",
        )
        
        async def mock_get_current_user():
            return mock_user
        
        app.dependency_overrides[get_current_user] = mock_get_current_user
        
        try:
            with (
                patch("app.api.v1.users.add_favorite_repo", new_callable=AsyncMock) as mock_add,
                patch("app.api.v1.users.list_favorite_repos", new_callable=AsyncMock) as mock_list,
            ):
                mock_list.return_value = [mock_repo]

                response = client.post(
                    "/api/v1/users/favorites",
                    json=mock_repo.model_dump(),
                    headers={"Authorization": "Bearer fake_token"},
                )

                assert response.status_code == 200
                data = response.json()
                assert len(data) == 1
        finally:
            app.dependency_overrides = {}

    def test_remove_favorite_success(self, client, mock_repo):
        mock_user = UserProfile(
            user_id="google:123456789",
            email="test@example.com",
            name="Test User",
            avatar_url="https://example.com/avatar.jpg",
            github_username="testuser",
        )
        
        async def mock_get_current_user():
            return mock_user
        
        app.dependency_overrides[get_current_user] = mock_get_current_user
        
        try:
            with (
                patch("app.api.v1.users.remove_favorite_repo", new_callable=AsyncMock) as mock_remove,
                patch("app.api.v1.users.list_favorite_repos", new_callable=AsyncMock) as mock_list,
            ):
                mock_list.return_value = []

                response = client.delete(
                    "/api/v1/users/favorites/12345",
                    headers={"Authorization": "Bearer fake_token"},
                )

                assert response.status_code == 200
                data = response.json()
                assert len(data) == 0
        finally:
            app.dependency_overrides = {}


class TestSavedSearches:
    def test_get_saved_searches_success(self, client, mock_saved_search):
        mock_user = UserProfile(
            user_id="google:123456789",
            email="test@example.com",
            name="Test User",
            avatar_url="https://example.com/avatar.jpg",
            github_username="testuser",
        )
        
        async def mock_get_current_user():
            return mock_user
        
        app.dependency_overrides[get_current_user] = mock_get_current_user
        
        try:
            with patch("app.api.v1.users.list_saved_searches", new_callable=AsyncMock) as mock_list:
                mock_list.return_value = [mock_saved_search]

                response = client.get(
                    "/api/v1/users/saved-searches",
                    headers={"Authorization": "Bearer fake_token"},
                )

                assert response.status_code == 200
                data = response.json()
                assert len(data) == 1
                assert data[0]["name"] == "My Search"
        finally:
            app.dependency_overrides = {}

    def test_create_saved_search_success(self, client, mock_saved_search):
        mock_user = UserProfile(
            user_id="google:123456789",
            email="test@example.com",
            name="Test User",
            avatar_url="https://example.com/avatar.jpg",
            github_username="testuser",
        )
        
        async def mock_get_current_user():
            return mock_user
        
        app.dependency_overrides[get_current_user] = mock_get_current_user
        
        try:
            with patch("app.api.v1.users.save_search", new_callable=AsyncMock) as mock_save:
                mock_save.return_value = mock_saved_search

                response = client.post(
                    "/api/v1/users/saved-searches",
                    json={"name": "My Search", "query": "python machine learning"},
                    headers={"Authorization": "Bearer fake_token"},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["name"] == "My Search"
                assert data["query"] == "python machine learning"
        finally:
            app.dependency_overrides = {}


class TestCollections:
    def test_get_collections_success(self, client):
        mock_user = UserProfile(
            user_id="google:123456789",
            email="test@example.com",
            name="Test User",
            avatar_url="https://example.com/avatar.jpg",
            github_username="testuser",
        )
        
        async def mock_get_current_user():
            return mock_user
        
        app.dependency_overrides[get_current_user] = mock_get_current_user
        
        try:
            with patch("app.api.v1.users.list_collections", new_callable=AsyncMock) as mock_list:
                mock_list.return_value = []

                response = client.get(
                    "/api/v1/users/collections",
                    headers={"Authorization": "Bearer fake_token"},
                )

                assert response.status_code == 200
                data = response.json()
                assert data == []
        finally:
            app.dependency_overrides = {}

    def test_create_collection_success(self, client):
        mock_user = UserProfile(
            user_id="google:123456789",
            email="test@example.com",
            name="Test User",
            avatar_url="https://example.com/avatar.jpg",
            github_username="testuser",
        )
        
        async def mock_get_current_user():
            return mock_user
        
        app.dependency_overrides[get_current_user] = mock_get_current_user
        
        collection_data = {
            "name": "Best Python Projects",
            "description": "My favorite Python repositories",
            "repo_ids": [12345, 67890],
        }
        
        try:
            with patch("app.api.v1.users.create_collection", new_callable=AsyncMock) as mock_create:
                mock_create.return_value = {"id": "coll123", **collection_data}

                response = client.post(
                    "/api/v1/users/collections",
                    json=collection_data,
                    headers={"Authorization": "Bearer fake_token"},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["name"] == "Best Python Projects"
                assert data["repo_ids"] == [12345, 67890]
        finally:
            app.dependency_overrides = {}


class TestRecommendations:
    def test_get_recommendations_success(self, client, mock_repo):
        mock_user = UserProfile(
            user_id="google:123456789",
            email="test@example.com",
            name="Test User",
            avatar_url="https://example.com/avatar.jpg",
            github_username="testuser",
        )
        
        async def mock_get_current_user():
            return mock_user
        
        app.dependency_overrides[get_current_user] = mock_get_current_user
        
        try:
            with (
                patch("app.api.v1.users.get_github_token", new_callable=AsyncMock) as mock_token,
                patch("app.api.v1.users.get_user_starred_repositories", new_callable=AsyncMock) as mock_starred,
                patch("app.api.v1.users.list_saved_searches", new_callable=AsyncMock) as mock_searches,
                patch("app.api.v1.users.search_github_repositories", new_callable=AsyncMock) as mock_search,
            ):
                mock_token.return_value = "fake_github_token"
                mock_starred.return_value = [mock_repo]
                mock_searches.return_value = []
                mock_search.return_value = [mock_repo]

                response = client.get(
                    "/api/v1/users/recommendations",
                    headers={"Authorization": "Bearer fake_token"},
                )

                assert response.status_code == 200
                data = response.json()
                assert len(data) == 1
                assert data[0]["id"] == 12345
        finally:
            app.dependency_overrides = {}