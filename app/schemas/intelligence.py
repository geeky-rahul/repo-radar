"""Repository intelligence schema definitions."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class PersonalizationIntent(BaseModel):
    experience_level: Optional[str] = Field(
        None,
        description="beginner, intermediate, or advanced",
    )
    goal: Optional[str] = Field(
        None,
        description="learning, production, contribution, or reference",
    )
    constraints: list[str] = Field(default_factory=list)


class RepositoryDeepSignals(BaseModel):
    recent_commits_30d: int = 0
    recent_commits_90d: int = 0
    contributor_count: int = 0
    issue_resolution_rate: float | None = None
    pr_merge_rate: float | None = None
    release_frequency_per_month: float = 0.0
    documentation_quality: float = Field(0.0, ge=0.0, le=1.0)
    dependency_freshness: float = Field(0.0, ge=0.0, le=1.0)
    open_issue_backlog_ratio: float = Field(0.0, ge=0.0, le=1.0)
    has_readme: bool = False
    readme_word_count: int = 0
    primary_language_count: int = 0
    architecture_pattern: str = "unknown"
    entry_points: list[str] = Field(default_factory=list)
    key_files: list[str] = Field(default_factory=list)
    core_modules: list[str] = Field(default_factory=list)
    summary: str | None = None


class RepositoryQualityAssessment(BaseModel):
    score: int = Field(..., ge=0, le=100)
    label: str
    insight: str
    factors: dict[str, float] = Field(default_factory=dict)
    clone_risk_warning: str | None = None


class RepositoryFitAssessment(BaseModel):
    score: int = Field(..., ge=0, le=100)
    explanation: str


class RepositorySummary(BaseModel):
    what_it_does: str
    how_it_works: str
    key_files: list[str] = Field(default_factory=list)
    complexity: str = Field(
        "Intermediate",
        description="Beginner, Intermediate, or Advanced",
    )
    primary_languages: list[str] = Field(default_factory=list)
    architecture_pattern: str = "unknown"
    entry_points: list[str] = Field(default_factory=list)
    core_modules: list[str] = Field(default_factory=list)
    setup_steps: list[str] = Field(default_factory=list)
    first_things_to_try: list[str] = Field(default_factory=list)
    common_issues: list[str] = Field(default_factory=list)


class RepositoryIntelligence(BaseModel):
    quality: RepositoryQualityAssessment
    fit: RepositoryFitAssessment | None = None
    summary: RepositorySummary | None = None
    clone_risk_warning: str | None = None
    trend_label: str | None = None
    trend_note: str | None = None
    maintenance_status: str | None = None
    documentation_quality: float | None = Field(None, ge=0.0, le=1.0)
    dependency_freshness: float | None = Field(None, ge=0.0, le=1.0)


class QueryRefinementSuggestion(BaseModel):
    message: str
    reason: str | None = None
    action: str | None = None


class ComparisonRepositoryRow(BaseModel):
    full_name: str
    language: str | None = None
    quality_score: int = Field(..., ge=0, le=100)
    fit_score: int = Field(..., ge=0, le=100)
    documentation_quality: float = Field(0.0, ge=0.0, le=1.0)
    maintenance_status: str
    community_activity: str
    setup_difficulty: str
    use_case_suitability: str
    label: str
    insight: str


class ComparisonRequest(BaseModel):
    repositories: list[str] = Field(..., min_length=2, max_length=5)
    intent: PersonalizationIntent | None = None


class ComparisonResponse(BaseModel):
    repositories: list[ComparisonRepositoryRow]
    conclusion: str
    best_for_beginners: str | None = None
    best_for_production: str | None = None
    most_active: str | None = None


class StarterGuide(BaseModel):
    repository: str
    install_dependencies: list[str] = Field(default_factory=list)
    environment_setup: list[str] = Field(default_factory=list)
    run_commands: list[str] = Field(default_factory=list)
    common_issues: list[str] = Field(default_factory=list)
    first_things_to_try: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RepositoryAnalysisResponse(BaseModel):
    repository: str
    intelligence: RepositoryIntelligence
    source_url: HttpUrl | None = None