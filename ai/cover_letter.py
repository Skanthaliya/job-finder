"""
ai/cover_letter.py — Phase 2 stub: Gemini AI cover letter generation.

This module will use the Google Gemini API to generate tailored
cover letters for specific job postings based on the user's profile.

NOT YET IMPLEMENTED — Phase 2.
"""

import logging

logger = logging.getLogger(__name__)


def generate_cover_letter(
    job: dict,
    profile: dict,
    language: str = "English",
) -> str:
    """
    Generate a tailored cover letter for a specific job using Gemini AI.

    Args:
        job: A job dict (unified schema) with description.
        profile: The user's profile dict (from my_profile.json).
        language: Language to write the cover letter in ("English", "German", etc.).

    Returns:
        Generated cover letter text.

    Raises:
        NotImplementedError: This feature is not yet implemented.
    """
    raise NotImplementedError(
        "Phase 2: AI cover letter generation not yet implemented. "
        "Will use Gemini API to create tailored cover letters in the specified language."
    )
