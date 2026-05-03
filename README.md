# GitHub Repository Search API

An AI-powered GitHub repository search backend built with **FastAPI** and **LangChain (LCEL)**.
Converts natural language queries into optimised GitHub search requests, ranks results, and returns clean structured JSON.

---

## Architecture

```
app/
├── main.py                  # FastAPI app factory + lifespan hooks
├── api/
│   └── v1/
│       ├── search.py        # POST /api/v1/search/repositories
│       ├── health.py        # GET  /api/v1/health
│       └── users.py         # Google auth, favorites, saved searches, recommendations
├── agents/
│   └── query_agent.py       # LangChain LCEL pipeline (LLM → ParsedGitHubQuery)
├── tools/
│   └── github_search.py     # Async GitHub Search API client
├── services/
│   ├── search.py            # Orchestration: cache → parse → fetch → rank
│   ├── ranking.py           # Composite scoring + sort
│   ├── cache.py             # Redis async cache (non-fatal on miss)
│   └── user.py              # User storage, sessions, favorites, saved searches, collections
├── schemas/
│   ├── search.py            # All Pydantic request/response models
│   └── user.py              # User profile, auth, saved search & collection schemas
├── core/
│   ├── config.py            # pydantic-settings (.env driven)
│   ├── logging.py           # structlog configuration
│   └── exceptions.py        # Typed exception hierarchy
└── utils/
    └── fallback_parser.py   # Rule-based query parser (LLM fallback)
```

### Request pipeline

```
POST /api/v1/search/repositories
        │
        ▼
   [Cache lookup] ──hit──► return cached SearchResponse
        │ miss
        ▼
  [Query Agent]  LangChain LCEL: ChatPromptTemplate | ChatGoogleGenerativeAI | PydanticOutputParser
        │  failure → fallback_parse_query (rule-based)
        ▼
  [Override merge] user-supplied language/min_stars/pushed_after/fork/archived/topic/license win
        │
        ▼
  [GitHub Tool]  async httpx → api.github.com/search/repositories
        │        qualifiers: stars:>=N language:X pushed:>=date fork:true/false archived:true/false topic:xyz license:MIT sort=stars
        ▼
  [Ranking]  composite score = 0.45·stars + 0.18·recency + 0.15·completeness + 0.10·activity + 0.08·health + 0.04·trend
        │
        ▼
  [Cache write]  Redis SETEX (TTL configurable)
        │
        ▼
  SearchResponse JSON
```

---

## Quick Start

### 1. Prerequisites

- Python 3.12+
- Redis (optional — app degrades gracefully without it)
- Gemini API key
- GitHub personal access token (increases rate limit from 10 to 5000 req/hr)

### 2. Install

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env — set GEMINI_API_KEY and GITHUB_TOKEN at minimum
```

### 4. Run

```bash
uvicorn app.main:app --reload
# API docs: http://localhost:8000/docs
```

---

## API Reference

### `POST /api/v1/search/repositories`

**Request**
```json
{
  "query": "best beginner python chatbot project",
  "language": "python",           // optional override
  "min_stars": 200,               // optional override
  "pushed_after": "2024-01-01",   // optional override (YYYY-MM-DD)
  "fork": false,                  // optional override — exclude forks
  "archived": false,              // optional override — exclude archived repos
  "topic": "cli",                 // optional override — filter by topic
  "license": "MIT",               // optional override — filter by license
  "top_k": 10                     // 1–30, default 10
}
```

**Response**
```json
{
  "original_query": "best beginner python chatbot project",
  "parsed_query": {
    "query": "chatbot beginner",
    "language": "python",
    "min_stars": 500,
    "pushed_after": null,
    "fork": null,
    "archived": false,
    "topic": null,
    "license": null
  },
  "total_found": 10,
  "results": [
    {
      "id": 123456,
      "name": "ChatterBot",
      "full_name": "gunthercox/ChatterBot",
      "html_url": "https://github.com/gunthercox/ChatterBot",
      "description": "ChatterBot is a machine learning, conversational dialog engine...",
      "stargazers_count": 13800,
      "forks_count": 3200,
      "language": "Python",
      "pushed_at": "2024-03-10T12:00:00Z",
      "created_at": "2015-01-01T00:00:00Z",
      "archived": false,
      "topics": ["chatbot", "machine-learning", "python"],
      "license_name": "BSD-3-Clause",
      "owner_login": "gunthercox",
      "score": 0.847321
    }
  ],
  "cached": false,
  "duration_ms": 423.1
}
```

**Error responses**

| Status | Code | Cause |
|--------|------|-------|
| 400 | `QUERY_PARSE_ERROR` | Both LLM and fallback parsing failed |
| 422 | — | Pydantic validation error (query too short/long, invalid top_k) |
| 429 | `GITHUB_RATE_LIMIT` | GitHub API rate limit exceeded |
| 502 | `GITHUB_API_ERROR` | GitHub API returned an error |
| 500 | `INTERNAL_ERROR` | Unexpected server error |

### User account features

Authentication is handled with Google sign-in and bearer sessions.

- `GET /api/v1/users/auth/config` — retrieve Google OAuth client configuration for frontend sign-in
- `POST /api/v1/users/auth/google` — authenticate with a Google ID token, optionally attach a GitHub token for personalization
- `GET /api/v1/users/auth/callback` — OAuth callback endpoint for Google authorization code flow
- `GET /api/v1/users/me` — retrieve the current user profile
- `GET /api/v1/users/favorites` — list favorite repositories
- `POST /api/v1/users/favorites` — add a repository to favorites
- `DELETE /api/v1/users/favorites/{repo_id}` — remove a favorite
- `GET /api/v1/users/saved-searches` — list saved searches
- `POST /api/v1/users/saved-searches` — save a search query
- `GET /api/v1/users/collections` — list repository collections
- `POST /api/v1/users/collections` — create a new collection
- `GET /api/v1/users/recommendations` — personalized feed derived from starred repos and saved searches

Use the header: `Authorization: Bearer <access_token>`

### `GET /api/v1/health`

```json
{ "status": "ok", "cache": "ok" }
```

---

## Ranking Algorithm

Each repository receives a composite score in `[0, 1]`:

```
score = 0.45·stars + 0.18·recency + 0.15·completeness + 0.10·activity + 0.08·health + 0.04·trend
```

| Component | Method |
|-----------|--------|
| `stars_score` | `log1p(stars) / log1p(200_000)` — log-normalised, capped at 200k |
| `recency_score` | `exp(-days_since_push / 730)` — exponential decay over ~2 years |
| `completeness_score` | Bonus for: description (+0.45), topics (+0.20), license (+0.15), language (+0.10), owner (+0.10) |
| `activity_score` | Combines recency and fork adoption to estimate contributor engagement |
| `health_score` | Community health from issue pressure and CI/CD workflow presence |
| `trend_score` | Estimates momentum via stars per day over repository lifetime |

Weights are configurable via environment variables:
```
RANKING_STARS_WEIGHT=0.45
RANKING_RECENCY_WEIGHT=0.18
RANKING_COMPLETENESS_WEIGHT=0.15
RANKING_ACTIVITY_WEIGHT=0.10
RANKING_HEALTH_WEIGHT=0.08
RANKING_TREND_WEIGHT=0.04
```

---

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | — | Required for LLM query parsing |
| `GITHUB_TOKEN` | — | Recommended (raises rate limit 10x) |
| `GOOGLE_OAUTH_CLIENT_ID` | — | Required to verify Google sign-in tokens |
| `LLM_MODEL` | `gemini-1.5-flash` | Gemini model for query parsing |
| `LLM_TEMPERATURE` | `0.0` | Deterministic LLM output |
| `REDIS_URL` | `redis://localhost:6379` | Cache backend |
| `CACHE_TTL_SECONDS` | `300` | Cache entry lifetime |
| `CACHE_ENABLED` | `true` | Disable cache during local testing |
| `GITHUB_API_BASE_URL` | `https://api.github.com` | GitHub REST API base URL |
| `GITHUB_SEARCH_MAX_RESULTS` | `10` | Max repos fetched per request |
| `GITHUB_REQUEST_TIMEOUT` | `10.0` | HTTP timeout in seconds |
| `APP_URL` | `http://localhost:8000` | Base application URL used for OAuth redirects |
| `APP_DEBUG` | `false` | Enable debug mode and permissive CORS for local development |
| `RANKING_STARS_WEIGHT` | `0.45` | Star count influence |
| `RANKING_RECENCY_WEIGHT` | `0.18` | Last push date influence |
| `RANKING_COMPLETENESS_WEIGHT` | `0.15` | Metadata completeness influence |
| `RANKING_ACTIVITY_WEIGHT` | `0.10` | Contributor activity influence |
| `RANKING_HEALTH_WEIGHT` | `0.08` | Community health influence |
| `RANKING_TREND_WEIGHT` | `0.04` | Star velocity influence |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `APP_ENV` | `development` | Set to `development` for local runs (pretty logs) |

---

## Running Tests

```bash
pytest tests/ -v
```

Tests use mocking — no live API keys or Redis required.

---

## Extending the System

**Add a new tool** (e.g., npm registry search):
1. Create `app/tools/npm_search.py` with an `async def search_npm_packages(...)` function
2. Add the tool call in `app/services/search.py`
3. Add new fields to `ParsedGitHubQuery` / `SearchRequest` if needed

**Swap the LLM provider:**
- Replace `ChatGoogleGenerativeAI` in `app/agents/query_agent.py` with any `langchain_*` chat model
- The LCEL chain `prompt | llm | parser` stays identical

**Add more ranking signals:**
- Add a new `_xxx_score()` function in `app/services/ranking.py`
- Introduce a new weight in `app/core/config.py` and wire it into `rank_repositories()`
