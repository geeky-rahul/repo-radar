import os
import pytest

# Set dummy env vars before any app imports so pydantic-settings doesn't error
os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("GITHUB_TOKEN", "ghp-test-token")
os.environ.setdefault("CACHE_ENABLED", "false")
