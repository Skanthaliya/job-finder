"""
ai/gemini_utils.py — Shared utilities for safe Gemini API interaction.

Provides safe response text extraction (handles blocked/empty responses)
and retry logic with exponential backoff for rate-limit (429) errors.
"""

import logging
import time

import google.generativeai as genai

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
INITIAL_BACKOFF = 5.0  # seconds


def safe_response_text(response) -> str | None:
    """Extract text from a Gemini response, returning None on blocked/empty content."""
    try:
        if not response.candidates:
            logger.warning("Gemini returned no candidates")
            return None

        candidate = response.candidates[0]
        finish_reason = getattr(candidate, "finish_reason", None)

        if finish_reason is not None:
            reason_name = finish_reason.name if hasattr(finish_reason, "name") else str(finish_reason)
            if reason_name in ("SAFETY", "RECITATION", "OTHER"):
                logger.warning("Gemini blocked response: finish_reason=%s", reason_name)
                return None

        text = response.text
        if not text or not text.strip():
            logger.warning("Gemini returned empty text")
            return None

        return text.strip()

    except (ValueError, AttributeError, IndexError) as e:
        logger.warning("Failed to extract Gemini response text: %s", e)
        return None


def generate_with_retry(
    model: genai.GenerativeModel,
    prompt: str,
    max_retries: int = MAX_RETRIES,
    initial_backoff: float = INITIAL_BACKOFF,
) -> str | None:
    """Call model.generate_content with retry on rate-limit (429) and transient errors.

    Returns the response text string, or None if all retries fail or response is blocked.
    """
    backoff = initial_backoff

    for attempt in range(max_retries + 1):
        try:
            response = model.generate_content(prompt)
            text = safe_response_text(response)
            return text

        except Exception as e:
            error_str = str(e).lower()
            is_rate_limit = "429" in error_str or "resource exhausted" in error_str or "quota" in error_str
            is_transient = "503" in error_str or "500" in error_str or "unavailable" in error_str

            if (is_rate_limit or is_transient) and attempt < max_retries:
                logger.warning(
                    "Gemini API error (attempt %d/%d): %s — retrying in %.1fs",
                    attempt + 1, max_retries + 1, e, backoff,
                )
                time.sleep(backoff)
                backoff *= 2
            else:
                logger.error("Gemini API call failed after %d attempts: %s", attempt + 1, e)
                return None

    return None
