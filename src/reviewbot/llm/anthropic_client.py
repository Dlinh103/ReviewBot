"""Anthropic Claude LLM client implementation."""

import asyncio
import logging
import time

from anthropic import APIConnectionError, AsyncAnthropic, InternalServerError, RateLimitError

from reviewbot.config import Settings, get_settings
from reviewbot.llm.base import LLMClient, LLMResponse

logger = logging.getLogger("reviewbot.llm.anthropic")

# Pricing per million tokens (Claude 3.5 / 4.6 Sonnet baseline)
INPUT_PRICE_PER_MILLION = 3.00
OUTPUT_PRICE_PER_MILLION = 15.00


def calculate_cost(input_tokens: int, output_tokens: int) -> float:
    """Calculate approximate USD cost for token usage."""
    input_cost = (input_tokens / 1_000_000) * INPUT_PRICE_PER_MILLION
    output_cost = (output_tokens / 1_000_000) * OUTPUT_PRICE_PER_MILLION
    return round(input_cost + output_cost, 6)


class AnthropicClient(LLMClient):
    """Async Anthropic API client conforming to LLMClient protocol."""

    def __init__(
        self,
        settings: Settings | None = None,
        async_anthropic: AsyncAnthropic | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = async_anthropic or AsyncAnthropic(
            api_key=self.settings.ANTHROPIC_API_KEY,
            timeout=float(self.settings.LLM_TIMEOUT_SECONDS),
        )
        self.model = self.settings.LLM_MODEL

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
        max_retries: int = 3,
    ) -> LLMResponse:
        """Call Claude to generate a JSON response with backoff retries."""
        limit_tokens = max_tokens or self.settings.LLM_MAX_TOKENS
        start_time = time.perf_counter()

        delay = 1.0
        last_exception: Exception | None = None

        for attempt in range(1, max_retries + 1):
            try:
                response = await self.client.messages.create(
                    model=self.model,
                    max_tokens=limit_tokens,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": user_prompt},
                    ],
                )

                duration_ms = int((time.perf_counter() - start_time) * 1000)
                content_text = ""
                for block in response.content:
                    if getattr(block, "type", "") == "text":
                        content_text += getattr(block, "text", "")

                in_tokens = response.usage.input_tokens
                out_tokens = response.usage.output_tokens
                cost = calculate_cost(in_tokens, out_tokens)

                logger.info(
                    "LLM call succeeded (%s) in %dms [in=%d, out=%d, cost=$%.4f]",
                    self.model,
                    duration_ms,
                    in_tokens,
                    out_tokens,
                    cost,
                )

                return LLMResponse(
                    content=content_text,
                    input_tokens=in_tokens,
                    output_tokens=out_tokens,
                    estimated_cost_usd=cost,
                    model=self.model,
                    duration_ms=duration_ms,
                )

            except (RateLimitError, InternalServerError, APIConnectionError) as exc:
                last_exception = exc
                logger.warning(
                    "Anthropic API error (%s) on attempt %d/%d: %s. Retrying in %ds...",
                    type(exc).__name__,
                    attempt,
                    max_retries,
                    exc,
                    int(delay),
                )
                if attempt == max_retries:
                    raise
                await asyncio.sleep(delay)
                delay *= 2

        raise last_exception or RuntimeError("Anthropic request failed unexpectedly")
