class AppBaseException(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class GitHubAPIError(AppBaseException):
    """Raised when GitHub API call fails."""


class GitHubRateLimitError(GitHubAPIError):
    """Raised when GitHub rate limit is exceeded."""


class QueryParsingError(AppBaseException):
    """Raised when AI/fallback query parsing fails."""


class LLMError(AppBaseException):
    """Raised when LLM invocation fails."""


class CacheError(AppBaseException):
    """Raised on cache read/write failures (non-fatal)."""
