"""User account and personalization schema definitions."""
from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class GoogleLoginRequest(BaseModel):
    id_token: str
    github_token: Optional[str] = None


class UserProfile(BaseModel):
    user_id: str
    email: EmailStr
    name: str
    avatar_url: Optional[str] = None
    github_username: Optional[str] = None
    github_token: Optional[str] = Field(None, exclude=True)


class UserProfileResponse(BaseModel):
    user_id: str
    email: EmailStr
    name: str
    avatar_url: Optional[str] = None
    github_username: Optional[str] = None


class AuthResponse(BaseModel):
    access_token: str
    user: UserProfileResponse


class SavedSearchCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    query: str = Field(..., min_length=3, max_length=256)


class SavedSearchItem(BaseModel):
    id: str
    name: str
    query: str


class CollectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    description: Optional[str] = None
    repo_ids: List[int] = Field(default_factory=list)


class CollectionItem(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    repo_ids: List[int] = Field(default_factory=list)
