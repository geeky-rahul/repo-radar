"""
Redis-backed async cache service.
Failures are non-fatal — the app degrades gracefully without caching.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json

import redis.asyncio as aioredis

from app.core.config import get_settings
from app.core.exceptions import CacheError
from app.core.logging import get_logger

logger = get_logger(__name__)

_redis_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis | None:
    global _redis_client
    settings = get_settings()
    if not settings.cache_enabled:
        return None
    if _redis_client is None:
        try:
            _redis_client = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2,
            )
            await _redis_client.ping()
            logger.info("cache.redis_connected")
        except Exception as exc:
            logger.warning("cache.redis_unavailable", error=str(exc))
            _redis_client = None
    return _redis_client


async def close_redis() -> None:
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None


def _cache_key(namespace: str, payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    digest = hashlib.sha256(canonical.encode()).hexdigest()[:16]
    return f"ghsearch:{namespace}:{digest}"


async def cache_get(namespace: str, payload: dict) -> dict | None:
    client = await get_redis()
    if client is None:
        return None
    key = _cache_key(namespace, payload)
    try:
        raw = await client.get(key)
        if raw:
            logger.debug("cache.hit", key=key)
            return json.loads(raw)
    except Exception as exc:
        logger.warning("cache.get_error", key=key, error=str(exc))
    return None


async def cache_set(namespace: str, payload: dict, value: dict) -> None:
    client = await get_redis()
    if client is None:
        return
    settings = get_settings()
    key = _cache_key(namespace, payload)
    try:
        await client.setex(key, settings.cache_ttl_seconds, json.dumps(value))
        logger.debug("cache.set", key=key, ttl=settings.cache_ttl_seconds)
    except Exception as exc:
        logger.warning("cache.set_error", key=key, error=str(exc))


def _repo_star_history_key(repo_id: int) -> str:
    return f"ghsearch:repo_star_history:{repo_id}"


async def get_repo_star_history(repo_id: int) -> dict[str, int] | None:
    client = await get_redis()
    if client is None:
        return None
    key = _repo_star_history_key(repo_id)
    try:
        raw = await client.get(key)
        if not raw:
            return None
        return json.loads(raw)
    except Exception as exc:
        logger.warning("cache.repo_history_get_error", key=key, error=str(exc))
        return None


async def update_repo_star_history(repo_id: int, stars: int) -> None:
    client = await get_redis()
    if client is None:
        return
    key = _repo_star_history_key(repo_id)
    now = datetime.now(tz=timezone.utc)
    now_iso = now.isoformat()

    current_data = await get_repo_star_history(repo_id)
    if current_data is None:
        payload = {
            "current": stars,
            "current_at": now_iso,
            "previous": stars,
            "previous_at": now_iso,
        }
    else:
        previous_at = current_data.get("current_at")
        try:
            previous_time = datetime.fromisoformat(previous_at)
        except Exception:
            previous_time = now

        if (now - previous_time).days >= 1:
            payload = {
                "current": stars,
                "current_at": now_iso,
                "previous": current_data.get("current", stars),
                "previous_at": previous_at,
            }
        else:
            payload = {
                "current": stars,
                "current_at": now_iso,
                "previous": current_data.get("previous", stars),
                "previous_at": current_data.get("previous_at", now_iso),
            }

    try:
        await client.set(key, json.dumps(payload))
    except Exception as exc:
        logger.warning("cache.repo_history_set_error", key=key, error=str(exc))
