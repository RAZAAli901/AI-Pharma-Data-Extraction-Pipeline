"""
Claude API Client — Wrapper around the Anthropic SDK for structured data extraction.

Handles API calls, rate limiting, retries, structured outputs,
and optional vision-based chart/image analysis.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import anthropic
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config.settings import settings
from pipeline.extraction.prompts import (
    SYSTEM_PROMPT,
    build_extraction_prompt,
    chunk_slides,
    get_extraction_schema,
)
from pipeline.extraction.schemas import ExtractedRecord, ExtractionResponse
from pipeline.ingestion.pptx_parser import PresentationContent, SlideContent

logger = logging.getLogger(__name__)


class ClaudeClient:
    """
    High-level client for extracting structured pharma data via Claude.

    Usage:
        client = ClaudeClient()
        records = client.extract(presentation_content)
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        max_retries: int | None = None,
    ):
        self._api_key = api_key or settings.anthropic_api_key
        self._model = model or settings.claude_model
        self._max_retries = max_retries or settings.max_retries

        if not self._api_key:
            raise ValueError(
                "Anthropic API key not configured. "
                "Set ANTHROPIC_API_KEY in your .env file."
            )

        self._client = anthropic.Anthropic(api_key=self._api_key)
        logger.info("Claude client initialized (model: %s)", self._model)

    # ── Public API ──────────────────────────────────────────────────────

    def extract(
        self,
        presentation: PresentationContent,
        enable_vision: bool | None = None,
    ) -> list[ExtractedRecord]:
        """
        Extract structured records from an entire presentation.

        Handles chunking, API calls, and aggregation of results.

        Args:
            presentation: Parsed presentation content.
            enable_vision: Whether to include slide images in the prompt.
                          Defaults to settings.enable_vision.

        Returns:
            List of validated ExtractedRecord objects.
        """
        if enable_vision is None:
            enable_vision = settings.enable_vision

        content_slides = presentation.content_slides
        if not content_slides:
            logger.warning("No content slides found in %s", presentation.file_name)
            return []

        # Render each slide to text
        slide_texts = [s.to_text(include_images=enable_vision) for s in content_slides]

        # Chunk slides to fit context window
        slide_chunks = chunk_slides(slide_texts)
        logger.info(
            "Processing %d content slides in %d chunk(s)",
            len(content_slides),
            len(slide_chunks),
        )

        all_records: list[ExtractedRecord] = []

        for chunk_idx, chunk_indices in enumerate(slide_chunks, 1):
            chunk_texts = [slide_texts[i] for i in chunk_indices]
            chunk_slides_obj = [content_slides[i] for i in chunk_indices]

            slide_start = chunk_slides_obj[0].slide_number
            slide_end = chunk_slides_obj[-1].slide_number

            logger.info(
                "Chunk %d/%d: slides %d–%d (%d slides)",
                chunk_idx,
                len(slide_chunks),
                slide_start,
                slide_end,
                len(chunk_indices),
            )

            # Build messages
            messages = self._build_messages(
                file_name=presentation.file_name,
                chunk_texts=chunk_texts,
                slide_start=slide_start,
                slide_end=slide_end,
                slides=chunk_slides_obj if enable_vision else None,
            )

            # Call Claude API with structured output
            response = self._call_api(messages)

            if response:
                # Stamp source info on each record
                for record in response.records:
                    record.source_file = presentation.file_name
                    record.slide_range = (
                        f"{slide_start}-{slide_end}"
                        if slide_start != slide_end
                        else str(slide_start)
                    )
                    record.extraction_timestamp = datetime.now(timezone.utc).isoformat()

                all_records.extend(response.records)
                logger.info(
                    "Chunk %d: extracted %d record(s)", chunk_idx, len(response.records)
                )

        logger.info(
            "Total: extracted %d record(s) from %s",
            len(all_records),
            presentation.file_name,
        )
        return all_records

    # ── Private Helpers ─────────────────────────────────────────────────

    def _build_messages(
        self,
        file_name: str,
        chunk_texts: list[str],
        slide_start: int,
        slide_end: int,
        slides: list[SlideContent] | None = None,
    ) -> list[dict[str, Any]]:
        """Build the messages array for the Claude API call."""
        user_content: list[dict[str, Any]] = []

        # Optionally include slide images for vision analysis
        if slides and settings.enable_vision:
            for slide in slides:
                for img in slide.images:
                    user_content.append(
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": img.content_type,
                                "data": img.base64_data,
                            },
                        }
                    )

        # Add the text extraction prompt
        prompt_text = build_extraction_prompt(
            file_name=file_name,
            slide_texts=chunk_texts,
            slide_start=slide_start,
            slide_end=slide_end,
        )
        user_content.append({"type": "text", "text": prompt_text})

        return [{"role": "user", "content": user_content}]

    @retry(
        retry=retry_if_exception_type(
            (anthropic.RateLimitError, anthropic.APIConnectionError)
        ),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(5),
        before_sleep=lambda retry_state: logger.warning(
            "Rate limited / connection error, retrying in %s seconds...",
            retry_state.next_action.sleep,  # type: ignore
        ),
    )
    def _call_api(self, messages: list[dict[str, Any]]) -> ExtractionResponse | None:
        """
        Call the Claude API with structured output format.

        Uses Anthropic's native structured outputs to guarantee
        schema-compliant JSON responses.
        """
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=8192,
                system=SYSTEM_PROMPT,
                messages=messages,
                output_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "extraction_response",
                        "schema": get_extraction_schema(),
                    },
                },
            )

            # Parse the structured response
            if response.content and len(response.content) > 0:
                raw_json = response.content[0].text
                extraction = ExtractionResponse.model_validate_json(raw_json)

                logger.debug(
                    "API response: %d records, %d input tokens, %d output tokens",
                    len(extraction.records),
                    response.usage.input_tokens,
                    response.usage.output_tokens,
                )
                return extraction

            logger.warning("Empty response from Claude API")
            return None

        except anthropic.BadRequestError as e:
            logger.error("Bad request to Claude API: %s", e)
            return None
        except json.JSONDecodeError as e:
            logger.error("Failed to parse Claude response as JSON: %s", e)
            return None
        except Exception as e:
            logger.error("Unexpected error calling Claude API: %s", e)
            raise

    def estimate_cost(self, presentation: PresentationContent) -> dict[str, float]:
        """
        Estimate the API cost for processing a presentation.

        Returns:
            Dict with estimated input_tokens, output_tokens, and cost_usd.
        """
        content_slides = presentation.content_slides
        total_chars = sum(len(s.to_text()) for s in content_slides)

        # Rough estimates: 1 token ≈ 4 chars, system prompt ≈ 500 tokens
        est_input_tokens = (total_chars // 4) + 500
        est_output_tokens = len(content_slides) * 800  # ~800 tokens per record

        # Claude Sonnet pricing (approximate)
        input_cost = (est_input_tokens / 1_000_000) * 3.0
        output_cost = (est_output_tokens / 1_000_000) * 15.0
        total_cost = input_cost + output_cost

        return {
            "estimated_input_tokens": est_input_tokens,
            "estimated_output_tokens": est_output_tokens,
            "estimated_cost_usd": round(total_cost, 4),
        }
