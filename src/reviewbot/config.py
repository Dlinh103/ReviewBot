"""Application configuration management using Pydantic Settings."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings schema and defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: str = "dev"
    LOG_LEVEL: str = "INFO"

    # GitHub App Configuration
    GITHUB_APP_ID: str = ""
    GITHUB_APP_PRIVATE_KEY_PATH: str = "./secrets/github-app.pem"
    GITHUB_WEBHOOK_SECRET: str = ""

    # LLM Configuration
    ANTHROPIC_API_KEY: str = ""
    LLM_MODEL: str = "claude-sonnet-4-6"
    LLM_MAX_TOKENS: int = 2000
    LLM_TIMEOUT_SECONDS: int = 60

    # Infrastructure
    DATABASE_URL: str = "postgresql+psycopg://reviewbot:reviewbot@localhost:5432/reviewbot"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Review Settings
    MAX_FILES_PER_PR: int = 40
    MAX_DIFF_TOKENS_PER_CHUNK: int = 6000
    MAX_COMMENTS_PER_PR: int = 15
    MIN_CONFIDENCE: float = 0.6
    REVIEW_DRAFT_PRS: bool = False
    OUTPUT_LANGUAGE: str = "vi"

    def get_private_key_content(self) -> str:
        """Read GitHub App private key from path if exists."""
        key_path = Path(self.GITHUB_APP_PRIVATE_KEY_PATH)
        if key_path.exists() and key_path.is_file():
            return key_path.read_text(encoding="utf-8")
        return ""


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
