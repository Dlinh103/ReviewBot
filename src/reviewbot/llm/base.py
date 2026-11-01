"""LLM Client interface abstraction and common response data structures."""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class LLMResponse:
    """Metadata and raw text response returned by an LLM provider."""

    content: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    model: str
    duration_ms: int


@runtime_checkable
class LLMClient(Protocol):
    """Protocol that all LLM provider clients must implement."""

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Call LLM and return structured raw text with usage telemetry."""
        ...
