from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = False
    log_level: str = "INFO"

    # Gemini
    gemini_api_key: str = ""

    # GitHub
    github_token: str = ""
    github_api_base_url: str = "https://api.github.com"
    github_search_max_results: int = 10
    github_request_timeout: float = 10.0

    # Redis
    redis_url: str = "redis://localhost:6379"
    cache_ttl_seconds: int = 300
    cache_enabled: bool = True

    # LLM
    llm_model: str = "gemini-1.5-flash"
    llm_temperature: float = 0.0
    llm_max_tokens: int = 512

    # Ranking weights
    ranking_stars_weight: float = 0.6
    ranking_recency_weight: float = 0.2
    ranking_completeness_weight: float = 0.2


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
