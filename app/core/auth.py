"""Authentication helper utilities and FastAPI dependencies."""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel

from app.schemas.user import UserProfile
from app.services.user import get_user_by_session_token, get_user_profile


class AuthenticatedUser(BaseModel):
    user: UserProfile


async def get_current_user(authorization: str | None = Header(None)) -> UserProfile:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing or invalid",
        )

    token = authorization.removeprefix("Bearer ").strip()
    user_id = await get_user_by_session_token(token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
        )

    user = await get_user_profile(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found for provided token",
        )

    return user
