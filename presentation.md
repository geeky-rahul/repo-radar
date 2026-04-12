# GitHub Repository Search API — Presentation

## 1. Project Overview

This project is an AI-powered backend for searching GitHub repositories. It exposes a FastAPI service that accepts natural language queries and converts them into optimized GitHub search requests. The system returns ranked, structured JSON results and supports optional caching via Redis.

Key goals:
- Convert a user query like "best beginner python chatbot project" into a precise GitHub search.
- Infer qualifiers such as language, minimum stars, and recency.
- Fetch repositories from the GitHub Search API.
- Rank results using stars, recency, and metadata completeness.
- Cache responses to reduce repeated GitHub requests.

## 2. Architecture

The app follows a layered architecture:

- `app/main.py`: FastAPI app factory, lifecycle hooks, exception handling, static file serving.
- `app/api/v1/search.py`: HTTP endpoint for repository search.
- `app/agents/query_agent.py`: LLM-based natural language parser with fallback.
- `app/tools/github_search.py`: GitHub Search API client.
- `app/services/search.py`: Orchestrator that wires caching, parsing, search, and ranking.
- `app/services/ranking.py`: Ranking algorithm for repository results.
- `app/services/cache.py`: Optional Redis cache.
- `app/utils/fallback_parser.py`: Rule-based query parser fallback.
- `app/core/config.py`: Settings and environment configuration.
- `app/schemas/search.py`: Pydantic request, response, and domain models.

## 3. Request Pipeline

A search request passes through the following stages:

1. API request enters `POST /api/v1/search/repositories`.
2. Validate request data with `SearchRequest`.
3. Attempt cache lookup using the full request payload.
4. Parse the natural language query into structured qualifiers.
5. Apply any user-provided overrides.
6. Build and execute the GitHub search query.
7. Rank returned repositories.
8. Cache the response.
9. Return a `SearchResponse`.

This flow ensures deterministic response structure and robust fallback behavior.

## 4. FastAPI App (`app/main.py`)

`app/main.py` is the entry point.

- Creates the FastAPI application via `create_app()`.
- Configures CORS based on `app_debug`.
- Registers routers for health and search endpoints.
- Mounts static files and serves `index.html` at `/` when available.
- Defines a global exception handler for `AppBaseException` subclasses so errors are serialized consistently.
- Manages startup/shutdown via `lifespan()`:
  - On startup, it warms up Redis.
  - On shutdown, it closes Redis.

## 5. Search API Layer (`app/api/v1/search.py`)

The endpoint accepts a `SearchRequest` model and forwards the request to `execute_search()`.

It also maps internal exceptions to HTTP responses:
- `QueryParsingError` → 400 `QUERY_PARSE_ERROR`
- `GitHubRateLimitError` → 429 `GITHUB_RATE_LIMIT`
- `GitHubAPIError` → 502 `GITHUB_API_ERROR`
- `LLMError` → 500 `LLM_ERROR`
- Any unexpected exception → 500 `INTERNAL_ERROR`

This layer is intentionally thin: it focuses on HTTP semantics, logging, and error translation.

## 6. Natural Language Parsing Agent (`app/agents/query_agent.py`)

### LLM-based parsing

The project uses LangChain LCEL and `ChatGoogleGenerativeAI` to parse natural language into `ParsedGitHubQuery`.

- System prompt defines the parser's role and extraction rules.
- Human prompt supplies `Natural language query: {user_query}`.
- `PydanticOutputParser` ensures the LLM output is validated and structured.

The target parsed fields are:
- `query`: clean keyword phrase for GitHub search.
- `language`: programming language if detected.
- `min_stars`: inferred popularity threshold.
- `pushed_after`: recency cutoff date.

### Fallback parser

If the Gemini key is missing or the LLM fails, `fallback_parse_query()` is used.

This ensures the app still works without the LLM, using deterministic rules.

## 7. Fallback Parser (`app/utils/fallback_parser.py`)

The rule-based parser extracts meaningful qualifiers from raw text.

It performs:
- Language detection from a list of known languages.
- Star threshold inference from keywords like `popular`, `best`, `beginner`.
- Recency detection from words such as `recent`, `new`, `latest`.
- Keyword cleaning by removing filler words and language names.

The resulting `ParsedGitHubQuery` is used exactly like the LLM output.

## 8. Search Orchestration (`app/services/search.py`)

`execute_search()` is the core pipeline:

- Start a timer.
- Build a cache key from the request payload.
- Check Redis cache with `cache_get()`.
- If cached, return the cached `SearchResponse` with `cached=True`.
- Parse the query via `parse_query()`.
- Apply user overrides (`language`, `min_stars`, `pushed_after`) using `_apply_overrides()`.
- Fetch repositories via `search_github_repositories()`.
- Rank results via `rank_repositories()`.
- Build the response payload.
- Write the response to cache asynchronously.

This service separates orchestration from transport and business logic.

## 9. GitHub Search Tool (`app/tools/github_search.py`)

This module handles GitHub search query assembly and HTTP communication.

### Query assembly

`_build_github_query()` constructs qualifiers:
- Base keyword query from `parsed.query`.
- `language:LANG` if present.
- `stars:>=N` if `min_stars` is positive.
- `pushed:>=YYYY-MM-DD` if recency is requested.

It also normalizes language tokens like `c++`, `c#`, and `go`.

### HTTP request

`search_github_repositories()` issues an async request to the GitHub Search API.

- Uses `httpx.AsyncClient` with configurable timeout.
- Sends `Accept: application/vnd.github+json` and optionally an Authorization header.
- Sorts by stars descending.
- Respects `top_k` and `GITHUB_SEARCH_MAX_RESULTS`.

### Error handling

It detects and raises:
- `GitHubRateLimitError` for 403 rate limit responses.
- `GitHubAPIError` for invalid queries, timeouts, network errors, or unexpected status codes.

### Retry logic

The call uses `tenacity` to retry network transport errors up to 3 times with exponential backoff.

## 10. Ranking Algorithm (`app/services/ranking.py`)

Repositories are ranked using a composite score in `[0, 1]`.

Score components:
- `stars_score`: log-normalized stars using `log1p` and a cap of 200,000.
- `recency_score`: exponential decay based on days since last push (`e^(-days/730)`).
- `completeness_score`: bonus metadata score based on description, topics, license, and language.

Default weights:
- Stars: 0.6
- Recency: 0.2
- Completeness: 0.2

The algorithm creates a new `RepositoryItem` with the computed `score`, then sorts descending.

## 11. Caching (`app/services/cache.py`)

Redis is used as an optional cache backend.

### Cache key

A deterministic key is derived from the request payload JSON:
- Sorted keys
- SHA256 digest truncated to 16 characters
- Namespaced with `ghsearch:search_v1`

### Behavior

- `cache_get()` returns cached JSON if Redis is available.
- `cache_set()` stores the serialized response with TTL from `CACHE_TTL_SECONDS`.
- Redis failures are non-fatal and logged as warnings.

This keeps caching from interfering with normal app behavior.

## 12. Data Models (`app/schemas/search.py`)

The schema models ensure strong validation and consistent API contracts.

### Request model
`SearchRequest`:
- `query`: required text
- `language`, `min_stars`, `pushed_after`: optional overrides
- `top_k`: result limit (1–30)

### Parsed query model
`ParsedGitHubQuery`:
- `query`, `language`, `min_stars`, `pushed_after`
- Validates `pushed_after` as `YYYY-MM-DD`

### Repository model
`RepositoryItem` includes GitHub metadata and the computed `score`.

### Response model
`SearchResponse` includes:
- `original_query`
- `parsed_query`
- `total_found`
- `results`
- `cached`
- `duration_ms`

## 13. Configuration (`app/core/config.py`)

Settings are loaded from `.env` via Pydantic `BaseSettings`.

Important variables:
- `GEMINI_API_KEY`: required for LLM parsing.
- `GITHUB_TOKEN`: optional but recommended.
- `LLM_MODEL`, `LLM_TEMPERATURE`, `LLM_MAX_TOKENS`
- `REDIS_URL`, `CACHE_TTL_SECONDS`, `CACHE_ENABLED`
- `GITHUB_SEARCH_MAX_RESULTS`, `GITHUB_REQUEST_TIMEOUT`
- Ranking weights: `RANKING_STARS_WEIGHT`, `RANKING_RECENCY_WEIGHT`, `RANKING_COMPLETENESS_WEIGHT`

`get_settings()` caches settings on first access to avoid repeated environment parsing.

## 14. Error Handling Strategy

The app uses typed exceptions and a central exception handler.

Custom exceptions include:
- `QueryParsingError`
- `GitHubRateLimitError`
- `GitHubAPIError`
- `LLMError`
- `CacheError`

These exceptions are raised inside the service layer and converted into JSON error responses at the API boundary.

## 15. Example Usage

Request:
```json
{
  "query": "best beginner python chatbot project",
  "language": "python",
  "min_stars": 200,
  "pushed_after": "2024-01-01",
  "top_k": 10
}
```

Response shape:
- `original_query`: raw user text
- `parsed_query`: LLM/fallback result
- `total_found`: number of returned repos
- `results`: list of ranked repositories with metadata and score
- `cached`: whether the response came from cache
- `duration_ms`: time spent executing the request

## 16. Extension Points

This project is designed to be extended easily:
- Add a new tool under `app/tools/` (e.g. NPM search).
- Swap the LLM provider by replacing `ChatGoogleGenerativeAI` in `app/agents/query_agent.py`.
- Add new ranking signals in `app/services/ranking.py` and expose weights in `app/core/config.py`.
- Add more request fields or response fields by extending `app/schemas/search.py`.

## 17. Summary

The GitHub Repository Search API is a modular backend built around:
- FastAPI for HTTP transport.
- LangChain + Gemini for natural language understanding.
- A fallback parser for reliability.
- A GitHub search tool for API integration.
- A scoring engine for ranking.
- Optional Redis caching.

Together, these pieces create a robust service for converting natural language intent into high-quality GitHub repository recommendations.
