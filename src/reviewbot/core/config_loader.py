"""Repository-specific review configuration loader (.reviewbot.yml)."""

import logging
from typing import Any

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger("reviewbot.core.config_loader")

CONFIG_FILENAMES = {".reviewbot.yml", ".reviewbot.yaml", ".github/.reviewbot.yml"}


class RepoConfig(BaseModel):
    """Configuration options parsed from .reviewbot.yml in target repository."""

    language: str = "vi"
    min_confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    max_comments: int = Field(default=15, ge=1, le=50)
    ignore: list[str] = Field(default_factory=list)
    focus: list[str] = Field(default_factory=list)
    rules: dict[str, Any] = Field(default_factory=dict)


def parse_repo_config(content: str) -> RepoConfig:
    """Parse raw YAML string into validated RepoConfig with graceful fallbacks."""
    if not content or not content.strip():
        return RepoConfig()

    try:
        data = yaml.safe_load(content)
        if not isinstance(data, dict):
            logger.warning("Invalid .reviewbot.yml format, expected a dict, got %s", type(data))
            return RepoConfig()

        return RepoConfig.model_validate(data)
    except Exception as exc:
        logger.warning("Failed to parse .reviewbot.yml: %s. Using default config.", exc)
        return RepoConfig()
