"""Alias routes for user-facing endpoints (singular /user/*) to match requested API surface."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends

from app.core.auth import get_current_user
from app.schemas.search import RepositoryItem
from app.schemas.user import CollectionCreate, CollectionItem
from app.schemas.user import UserProfile, UserProfileResponse
from app.services.user import (
    list_favorite_repos,
    add_favorite_repo,
    remove_favorite_repo,
    list_collections,
    create_collection,
    update_collection,
    delete_collection,
    add_repo_to_collection,
    remove_repo_from_collection,
    get_github_token,
)
from app.tools.github_search import search_github_repositories
from app.schemas.search import ParsedGitHubQuery

router = APIRouter(prefix="/user", tags=["user"])


@router.get("/profile", response_model=UserProfileResponse)
async def profile(user: UserProfile = Depends(get_current_user)) -> UserProfileResponse:
    return UserProfileResponse(
        user_id=user.user_id,
        email=user.email,
        name=user.name,
        avatar_url=user.avatar_url,
        github_username=user.github_username,
    )


@router.get("/favorites", response_model=List[RepositoryItem])
async def favorites(user: UserProfile = Depends(get_current_user)) -> List[RepositoryItem]:
    return await list_favorite_repos(user.user_id)


@router.post("/favorites", response_model=List[RepositoryItem])
async def add_favorite(repo: RepositoryItem, user: UserProfile = Depends(get_current_user)) -> List[RepositoryItem]:
    await add_favorite_repo(user.user_id, repo)
    return await list_favorite_repos(user.user_id)


@router.delete("/favorites/{repo_id}", response_model=List[RepositoryItem])
async def delete_favorite(repo_id: int, user: UserProfile = Depends(get_current_user)) -> List[RepositoryItem]:
    await remove_favorite_repo(user.user_id, repo_id)
    return await list_favorite_repos(user.user_id)


@router.get("/collections", response_model=List[CollectionItem])
async def collections(user: UserProfile = Depends(get_current_user)) -> List[CollectionItem]:
    return await list_collections(user.user_id)


@router.post("/collections", response_model=CollectionItem)
async def create_collection_endpoint(data: CollectionCreate, user: UserProfile = Depends(get_current_user)) -> CollectionItem:
    return await create_collection(user.user_id, data)


@router.put("/collections/{id}", response_model=CollectionItem)
async def update_collection_endpoint(id: str, data: CollectionCreate, user: UserProfile = Depends(get_current_user)) -> CollectionItem:
    return await update_collection(user.user_id, id, data)


@router.delete("/collections/{id}")
async def delete_collection_endpoint(id: str, user: UserProfile = Depends(get_current_user)) -> None:
    await delete_collection(user.user_id, id)


@router.post("/collections/{id}/add-repo", response_model=CollectionItem)
async def add_repo_to_collection_endpoint(id: str, repo_id: int, user: UserProfile = Depends(get_current_user)) -> CollectionItem:
    return await add_repo_to_collection(user.user_id, id, repo_id)


@router.delete("/collections/{id}/remove-repo", response_model=CollectionItem)
async def remove_repo_from_collection_endpoint(id: str, repo_id: int, user: UserProfile = Depends(get_current_user)) -> CollectionItem:
    return await remove_repo_from_collection(user.user_id, id, repo_id)


@router.get("/recommendations", response_model=List[RepositoryItem])
async def recommendations(user: UserProfile = Depends(get_current_user), top_k: int = 10) -> List[RepositoryItem]:
    # Lightweight recommendations placeholder (delegates to search-based recommendations)
    parsed = ParsedGitHubQuery(query="best trending open-source", min_stars=50)
    results = await search_github_repositories(parsed, top_k=top_k)
    return results
