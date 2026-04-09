from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.cache import get_redis

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    cache: str


@router.get("/health", response_model=HealthResponse, summary="Health check")
async def health() -> HealthResponse:
    redis = await get_redis()
    cache_status = "ok" if redis else "unavailable"
    return HealthResponse(status="ok", cache=cache_status)
