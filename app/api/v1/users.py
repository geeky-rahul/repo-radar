"""User-facing API endpoints for accounts, favorites, saved searches, and recommendations."""
from __future__ import annotations

from collections import Counter
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
import httpx

from app.core.auth import get_current_user
from app.core.config import get_settings
from app.core.exceptions import GitHubAPIError
from app.schemas.search import ParsedGitHubQuery, RepositoryItem
from app.schemas.user import (
    AuthResponse,
    CollectionCreate,
    CollectionItem,
    GoogleLoginRequest,
    SavedSearchCreate,
    SavedSearchItem,
    UserProfile,
    UserProfileResponse,
)
from app.tools.github_search import (
    get_github_user_info,
    get_user_starred_repositories,
    search_github_repositories,
)
from app.services.user import (
    add_favorite_repo,
    create_collection,
    create_or_update_user_profile,
    create_session_for_user,
    get_github_token,
    get_user_profile,
    list_collections,
    list_favorite_repos,
    list_saved_searches,
    remove_favorite_repo,
    save_search,
    update_user_github_token,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/auth/config", summary="Get OAuth configuration")
async def get_oauth_config():
    """Returns the Google OAuth client ID for frontend OAuth flow."""
    settings = get_settings()
    if not settings.google_oauth_client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth client ID is not configured.",
        )
    return {"client_id": settings.google_oauth_client_id}

def _to_public_profile(user: UserProfile) -> UserProfileResponse:
    return UserProfileResponse(
        user_id=user.user_id,
        email=user.email,
        name=user.name,
        avatar_url=user.avatar_url,
        github_username=user.github_username,
    )


@router.post("/auth/google", response_model=AuthResponse, summary="Sign in with Google")
async def google_login(request: GoogleLoginRequest) -> AuthResponse:
    settings = get_settings()
    if not settings.google_oauth_client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth client ID is not configured.",
        )

    try:
        id_info = id_token.verify_oauth2_token(
            request.id_token,
            google_requests.Request(),
            settings.google_oauth_client_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google ID token: {str(exc)}",
        ) from exc

    user_id = f"google:{id_info['sub']}"
    profile = UserProfile(
        user_id=user_id,
        email=id_info.get("email"),
        name=id_info.get("name", id_info.get("email", user_id)),
        avatar_url=id_info.get("picture"),
    )

    if request.github_token:
        try:
            github_user = await get_github_user_info(request.github_token)
            profile.github_username = github_user.get("login")
            profile.github_token = request.github_token
        except GitHubAPIError:
            pass

    await create_or_update_user_profile(profile)
    access_token = await create_session_for_user(user_id)

    return AuthResponse(access_token=access_token, user=_to_public_profile(profile))


@router.get("/auth/callback", summary="Google OAuth callback")
async def google_callback(code: str = Query(...), state: str = Query(None)) -> RedirectResponse:
    """
    Callback endpoint for Google OAuth 2.0 authorization code flow.
    Exchanges the authorization code for an ID token and creates a user session.
    """
    settings = get_settings()
    if not settings.google_oauth_client_id or not settings.google_oauth_client_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth credentials are not configured.",
        )

    try:
        # Exchange authorization code for ID token
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": settings.google_oauth_client_id,
                    "client_secret": settings.google_oauth_client_secret,
                    "redirect_uri": f"{settings.app_url}/api/v1/users/auth/callback",
                    "grant_type": "authorization_code",
                },
            )

            if not token_response.is_success:
                logger.error("OAuth callback: Token exchange failed",
                           status=token_response.status_code,
                           response=token_response.text)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to exchange authorization code for tokens.",
                )

            token_data = token_response.json()

        id_token_str = token_data.get("id_token")
        if not id_token_str:
            logger.error("OAuth callback: No ID token in response", token_data_keys=list(token_data.keys()))
            raise ValueError("No ID token in response")

        # Verify the ID token
        id_info = id_token.verify_oauth2_token(
            id_token_str,
            google_requests.Request(),
            settings.google_oauth_client_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("OAuth callback: Unexpected error during OAuth flow")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OAuth callback failed: {str(exc)}",
        ) from exc

    try:
        # Create/update user profile
        user_id = f"google:{id_info['sub']}"
        profile = UserProfile(
            user_id=user_id,
            email=id_info.get("email"),
            name=id_info.get("name", id_info.get("email", user_id)),
            avatar_url=id_info.get("picture"),
        )

        await create_or_update_user_profile(profile)
        access_token = await create_session_for_user(user_id)

        # Redirect back to homepage with access token in URL
        return RedirectResponse(
            url=f"/?token={access_token}&name={profile.name}",
            status_code=status.HTTP_302_FOUND,
        )
    except Exception as exc:
        logger.exception("OAuth callback: Error during user creation/session")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"User creation failed: {str(exc)}",
        ) from exc

@router.get("/me", response_model=UserProfileResponse, summary="Get current user profile")
async def get_current_profile(user: UserProfile = Depends(get_current_user)) -> UserProfileResponse:
    return _to_public_profile(user)


@router.get("/favorites", response_model=List[RepositoryItem], summary="List favorite repositories")
async def get_favorites(user: UserProfile = Depends(get_current_user)) -> List[RepositoryItem]:
    return await list_favorite_repos(user.user_id)


@router.post("/favorites", response_model=List[RepositoryItem], summary="Add a repository to favorites")
async def add_favorite(repo: RepositoryItem, user: UserProfile = Depends(get_current_user)) -> List[RepositoryItem]:
    await add_favorite_repo(user.user_id, repo)
    return await list_favorite_repos(user.user_id)


@router.delete("/favorites/{repo_id}", response_model=List[RepositoryItem], summary="Remove a repository from favorites")
async def remove_favorite(repo_id: int, user: UserProfile = Depends(get_current_user)) -> List[RepositoryItem]:
    await remove_favorite_repo(user.user_id, repo_id)
    return await list_favorite_repos(user.user_id)


@router.get("/saved-searches", response_model=List[SavedSearchItem], summary="List saved searches")
async def get_saved_searches(user: UserProfile = Depends(get_current_user)) -> List[SavedSearchItem]:
    return await list_saved_searches(user.user_id)


@router.post("/saved-searches", response_model=SavedSearchItem, summary="Save a new search")
async def create_saved_search(data: SavedSearchCreate, user: UserProfile = Depends(get_current_user)) -> SavedSearchItem:
    return await save_search(user.user_id, data)


@router.get("/collections", response_model=List[CollectionItem], summary="List collections")
async def get_collections(user: UserProfile = Depends(get_current_user)) -> List[CollectionItem]:
    return await list_collections(user.user_id)


@router.post("/collections", response_model=CollectionItem, summary="Create a collection")
async def create_collection_endpoint(data: CollectionCreate, user: UserProfile = Depends(get_current_user)) -> CollectionItem:
    return await create_collection(user.user_id, data)


@router.get("/recommendations", response_model=List[RepositoryItem], summary="Get personalized recommendations")
async def get_recommendations(user: UserProfile = Depends(get_current_user), top_k: int = 10) -> List[RepositoryItem]:
    github_token = await get_github_token(user.user_id)
    topics: list[str] = []
    languages: list[str] = []

    if github_token:
        try:
            starred = await get_user_starred_repositories(github_token, per_page=20)
            topics = [topic for repo in starred for topic in repo.topics if topic]
            languages = [repo.language for repo in starred if repo.language]
        except GitHubAPIError:
            topics = []
            languages = []

    saved_searches = await list_saved_searches(user.user_id)
    query_terms: list[str] = []
    if topics:
        query_terms.extend([topic for topic, _ in Counter(topics).most_common(3)])
    if not query_terms and saved_searches:
        query_terms.extend(saved_searches[0].query.split())
    if not query_terms:
        query_terms = ["best", "trending", "open-source"]

    language = Counter(languages).most_common(1)[0][0] if languages else None
    parsed = ParsedGitHubQuery(
        query=" ".join(query_terms[:6]),
        language=language,
        min_stars=100,
    )

    results = await search_github_repositories(parsed, top_k=top_k)
    return results
