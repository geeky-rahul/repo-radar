"""User account persistence and personalization storage."""
from __future__ import annotations

import json
import secrets
from uuid import uuid4
from typing import Dict

from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.search import RepositoryItem
from app.schemas.user import CollectionCreate, CollectionItem, SavedSearchCreate, SavedSearchItem, UserProfile
from app.services.cache import get_redis

logger = get_logger(__name__)

_SESSION_TTL = 30 * 24 * 60 * 60

# Temporary in-memory session store for when Redis is unavailable
_temp_sessions: Dict[str, str] = {}


def _profile_key(user_id: str) -> str:
    return f"ghsearch:user:{user_id}:profile"


def _session_key(token: str) -> str:
    return f"ghsearch:session:{token}"


def _favorites_key(user_id: str) -> str:
    return f"ghsearch:user:{user_id}:favorites"


def _saved_searches_key(user_id: str) -> str:
    return f"ghsearch:user:{user_id}:saved_searches"


def _collections_key(user_id: str) -> str:
    return f"ghsearch:user:{user_id}:collections"


async def get_user_profile(user_id: str) -> UserProfile | None:
    redis = await get_redis()
    if redis is None:
        return None
    raw = await redis.get(_profile_key(user_id))
    if not raw:
        return None
    return UserProfile.model_validate(json.loads(raw))


async def create_or_update_user_profile(profile: UserProfile) -> None:
    redis = await get_redis()
    if redis is None:
        logger.warning("create_or_update_user_profile: Redis unavailable, skipping profile storage")
        return
    await redis.set(_profile_key(profile.user_id), json.dumps(profile.model_dump()))


async def get_user_by_session_token(token: str) -> str | None:
    redis = await get_redis()
    if redis is not None:
        return await redis.get(_session_key(token))

    # Fallback to temporary in-memory store
    return _temp_sessions.get(token)


async def create_session_for_user(user_id: str) -> str:
    redis = await get_redis()
    token = secrets.token_urlsafe(32)

    if redis is not None:
        settings = get_settings()
        ttl = getattr(settings, "user_session_ttl_seconds", _SESSION_TTL)
        await redis.setex(_session_key(token), ttl, user_id)
    else:
        logger.warning("create_session_for_user: Redis unavailable, using temporary in-memory session")
        # Store in temporary memory (not persistent, but allows login to work)
        _temp_sessions[token] = user_id

    return token


async def add_favorite_repo(user_id: str, repo: RepositoryItem) -> None:
    redis = await get_redis()
    if redis is None:
        return
    await redis.hset(_favorites_key(user_id), mapping={str(repo.id): json.dumps(repo.model_dump())})


async def remove_favorite_repo(user_id: str, repo_id: int) -> None:
    redis = await get_redis()
    if redis is None:
        return
    await redis.hdel(_favorites_key(user_id), str(repo_id))


async def list_favorite_repos(user_id: str) -> list[RepositoryItem]:
    redis = await get_redis()
    if redis is None:
        return []
    values = await redis.hvals(_favorites_key(user_id))
    return [RepositoryItem.model_validate(json.loads(raw)) for raw in values if raw]


async def save_search(user_id: str, data: SavedSearchCreate) -> SavedSearchItem:
    redis = await get_redis()
    if redis is None:
        raise RuntimeError("Redis is required for saved searches")
    search_id = uuid4().hex
    item = SavedSearchItem(id=search_id, name=data.name, query=data.query)
    await redis.hset(_saved_searches_key(user_id), mapping={search_id: json.dumps(item.model_dump())})
    return item


async def list_saved_searches(user_id: str) -> list[SavedSearchItem]:
    redis = await get_redis()
    if redis is None:
        return []
    values = await redis.hvals(_saved_searches_key(user_id))
    return [SavedSearchItem.model_validate(json.loads(raw)) for raw in values if raw]


async def create_collection(user_id: str, collection: CollectionCreate) -> CollectionItem:
    redis = await get_redis()
    if redis is None:
        raise RuntimeError("Redis is required for collections")
    collection_id = uuid4().hex
    item = CollectionItem(
        id=collection_id,
        name=collection.name,
        description=collection.description,
        repo_ids=collection.repo_ids,
    )
    await redis.hset(_collections_key(user_id), mapping={collection_id: json.dumps(item.model_dump())})
    return item


async def list_collections(user_id: str) -> list[CollectionItem]:
    redis = await get_redis()
    if redis is None:
        return []
    values = await redis.hvals(_collections_key(user_id))
    return [CollectionItem.model_validate(json.loads(raw)) for raw in values if raw]


async def update_user_github_token(user_id: str, github_token: str, github_username: str | None = None) -> None:
    profile = await get_user_profile(user_id)
    if not profile:
        return
    profile.github_token = github_token
    if github_username:
        profile.github_username = github_username
    await create_or_update_user_profile(profile)


async def get_github_token(user_id: str) -> str | None:
    profile = await get_user_profile(user_id)
    return profile.github_token if profile else None
