"""Personalization and fit scoring helpers."""
from __future__ import annotations

from app.schemas.intelligence import PersonalizationIntent, RepositoryDeepSignals, RepositoryFitAssessment
from app.schemas.search import RepositoryItem, SearchRequest
from app.services.scoring_service import _fit_score, build_lightweight_signals, build_intent_from_search_request


def build_intent(request: SearchRequest) -> PersonalizationIntent | None:
    return build_intent_from_search_request(request)


def evaluate_fit(
    repo: RepositoryItem,
    intent: PersonalizationIntent | None,
    signals: RepositoryDeepSignals | None = None,
) -> RepositoryFitAssessment | None:
    if signals is None:
        signals = build_lightweight_signals(repo)
    return _fit_score(repo, signals, intent)
