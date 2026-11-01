"""High-level LLM review and summarization functions with automatic schema validation."""

import json
import logging
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from reviewbot.core.chunker import DiffChunk
from reviewbot.llm.base import LLMClient, LLMResponse
from reviewbot.llm.prompts import (
    REVIEW_SYSTEM_PROMPT,
    SUMMARY_SYSTEM_PROMPT_EN,
    SUMMARY_SYSTEM_PROMPT_VI,
    build_retry_user_prompt,
    build_review_user_prompt,
    build_summary_user_prompt,
)
from reviewbot.llm.schemas import PRSummary, ReviewResult

logger = logging.getLogger("reviewbot.llm.reviewer")

T = TypeVar("T", bound=BaseModel)


def extract_json_payload(raw_text: str) -> str:
    """Extract raw JSON substring from markdown code blocks or raw prose."""
    cleaned = raw_text.strip()
    # Match ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if match:
        return match.group(1).strip()
    return cleaned


async def parse_and_validate_with_retry(
    llm_client: LLMClient,
    system_prompt: str,
    initial_user_prompt: str,
    target_schema: type[T],
    max_parse_retries: int = 2,
) -> tuple[T, LLMResponse]:
    """Execute LLM call and validate output against target Pydantic schema with retries."""
    total_input_tokens = 0
    total_output_tokens = 0
    total_cost = 0.0
    total_duration_ms = 0
    last_raw_text = ""

    current_user_prompt = initial_user_prompt

    for attempt in range(max_parse_retries + 1):
        response = await llm_client.generate_json(
            system_prompt=system_prompt,
            user_prompt=current_user_prompt,
        )
        total_input_tokens += response.input_tokens
        total_output_tokens += response.output_tokens
        total_cost += response.estimated_cost_usd
        total_duration_ms += response.duration_ms
        last_raw_text = response.content

        extracted_json = extract_json_payload(response.content)

        try:
            # 1. Parse JSON syntax
            json_obj = json.loads(extracted_json)
            # 2. Validate with Pydantic
            validated = target_schema.model_validate(json_obj)

            combined_response = LLMResponse(
                content=last_raw_text,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                estimated_cost_usd=round(total_cost, 6),
                model=response.model,
                duration_ms=total_duration_ms,
            )
            return validated, combined_response

        except (json.JSONDecodeError, ValidationError) as err:
            logger.warning(
                "JSON validation failed on attempt %d/%d for %s: %s",
                attempt + 1,
                max_parse_retries + 1,
                target_schema.__name__,
                err,
            )
            if attempt == max_parse_retries:
                logger.error("Exhausted retries parsing LLM JSON for %s", target_schema.__name__)
                raise ValueError(
                    f"Failed to obtain valid JSON from LLM for {target_schema.__name__}: {err}\n"
                    f"Raw output:\n{last_raw_text}"
                ) from err

            # Build feedback prompt with exact error
            current_user_prompt = build_retry_user_prompt(
                error_message=str(err),
                invalid_output=last_raw_text,
                target_schema=target_schema,
            )

    raise RuntimeError("Unexpected loop exit in parse_and_validate_with_retry")


async def review_chunk(
    llm_client: LLMClient,
    chunk: DiffChunk,
    pr_title: str,
    pr_description: str,
    context: str = "",
    language: str = "",
) -> tuple[ReviewResult, LLMResponse]:
    """Review a single diff chunk using LLM and return validated ReviewResult."""
    user_prompt = build_review_user_prompt(
        title=pr_title,
        description=pr_description,
        language=language,
        path=chunk.file_path,
        numbered_diff=chunk.numbered_diff,
        context=context,
    )

    result, telemetry = await parse_and_validate_with_retry(
        llm_client=llm_client,
        system_prompt=REVIEW_SYSTEM_PROMPT,
        initial_user_prompt=user_prompt,
        target_schema=ReviewResult,
    )
    return result, telemetry


async def summarize_pr(
    llm_client: LLMClient,
    pr_title: str,
    pr_description: str,
    diff_overview: str,
    output_language: str = "vi",
) -> tuple[PRSummary, LLMResponse]:
    """Generate high-level PR summary and risk analysis using LLM."""
    system_prompt = (
        SUMMARY_SYSTEM_PROMPT_VI if output_language.lower() == "vi" else SUMMARY_SYSTEM_PROMPT_EN
    )
    user_prompt = build_summary_user_prompt(
        title=pr_title,
        description=pr_description,
        diff_overview=diff_overview,
    )

    summary, telemetry = await parse_and_validate_with_retry(
        llm_client=llm_client,
        system_prompt=system_prompt,
        initial_user_prompt=user_prompt,
        target_schema=PRSummary,
    )
    return summary, telemetry
