"""
ai/resume_tailor.py — Phase 2 stub: Gemini AI resume bullet tailoring.

This module will use the Google Gemini API to generate tailored
resume bullet points optimized for specific job postings.

NOT YET IMPLEMENTED — Phase 2.
"""

import logging

logger = logging.getLogger(__name__)


def generate_tailored_bullets(
    job: dict,
    profile: dict,
) -> str:
    """
    Generate tailored resume bullet points for a specific job using Gemini AI.

    Takes the user's existing experience and rewrites/optimizes bullet points
    to align with the job description, emphasizing relevant skills and achievements.

    Args:
        job: A job dict (unified schema) with description.
        profile: The user's profile dict (from my_profile.json).

    Returns:
        Formatted string of tailored resume bullet points.

    Raises:
        NotImplementedError: This feature is not yet implemented.
    """
    raise NotImplementedError(
        "Phase 2: AI resume tailoring not yet implemented. "
        "Will use Gemini API to customize resume bullets for each job."
    )
