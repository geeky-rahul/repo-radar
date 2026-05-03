from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, HttpUrl, field_validator


# ─── Request ──────────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=256, description="Natural language search query")
    language: Optional[str] = Field(None, description="Filter by programming language")
    min_stars: Optional[int] = Field(None, ge=0, description="Minimum star count override")
    pushed_after: Optional[str] = Field(None, description="Only repos pushed after this date (YYYY-MM-DD)")
    fork: Optional[bool] = Field(None, description="Include forks when true, exclude forks when false")
    archived: Optional[bool] = Field(None, description="Include archived repos when true, exclude when false")
    topic: Optional[str] = Field(None, description="Filter by repository topic")
    license: Optional[str] = Field(None, description="Filter by repository license identifier")
    top_k: int = Field(10, ge=1, le=30, description="Number of results to return")


# ─── Parsed query (LLM output) ────────────────────────────────────────────────

class ParsedGitHubQuery(BaseModel):
    """Structured output produced by the LLM query-parsing agent."""

    query: str = Field(..., description="Cleaned keyword search string for GitHub")
    language: Optional[str] = Field(None, description="Primary programming language if detected")
    min_stars: int = Field(0, ge=0, description="Minimum stars inferred from query intent")
    pushed_after: Optional[str] = Field(
        None,
        description="ISO date string YYYY-MM-DD — only set when recency is explicitly implied",
    )
    fork: Optional[bool] = Field(None, description="Include forks when true, exclude forks when false")
    archived: Optional[bool] = Field(None, description="Include archived repos when true, exclude when false")
    topic: Optional[str] = Field(None, description="Filter by repository topic")
    license: Optional[str] = Field(None, description="Filter by repository license identifier")

    @field_validator("pushed_after")
    @classmethod
    def validate_date(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("pushed_after must be YYYY-MM-DD") from exc
        return v


# ─── GitHub raw item ──────────────────────────────────────────────────────────

class RepositoryItem(BaseModel):
    id: int
    name: str
    full_name: str
    html_url: str
    description: Optional[str] = None
    stargazers_count: int = 0
    forks_count: int = 0
    open_issues_count: int = 0
    language: Optional[str] = None
    pushed_at: Optional[str] = None
    created_at: Optional[str] = None
    topics: list[str] = Field(default_factory=list)
    license_name: Optional[str] = None
    archived: bool = False
    owner_login: str
    owner_avatar_url: Optional[str] = None
    stars_yesterday: Optional[int] = Field(
        None,
        description="Previous recorded star count used for 24h trend scoring",
    )
    score: float = 0.0  # computed ranking score


# ─── Response ─────────────────────────────────────────────────────────────────

class SearchResponse(BaseModel):
    original_query: str
    parsed_query: ParsedGitHubQuery
    total_found: int
    results: list[RepositoryItem]
    cached: bool = False
    duration_ms: float = 0.0


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorDetail
