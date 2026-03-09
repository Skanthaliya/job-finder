"""
ai/scorer.py — Phase 2 stub: Gemini AI job scoring.

This module will use the Google Gemini API to score job postings
against the user's profile, providing a relevance score and reasoning.

NOT YET IMPLEMENTED — Phase 2.
"""

import logging

logger = logging.getLogger(__name__)


def score_job(job: dict, profile: dict) -> dict:
    """
    Score a single job against the user's profile using Gemini AI.

    Args:
        job: A job dict (unified schema).
        profile: The user's profile dict (from my_profile.json).

    Returns:
        Dict with keys: score (int 1-100), reasoning (str), pros (list), cons (list).

    Raises:
        NotImplementedError: This feature is not yet implemented.
    """
    raise NotImplementedError(
        "Phase 2: AI job scoring not yet implemented. "
        "Will use Gemini API to score jobs against your profile."
    )


def score_jobs_batch(
    jobs: list[dict],
    profile: dict,
    top_n: int = 50,
) -> list[dict]:
    """
    Score a batch of jobs against the user's profile and return the top N.

    Args:
        jobs: List of job dicts (unified schema).
        profile: The user's profile dict (from my_profile.json).
        top_n: Number of top-scored jobs to return.

    Returns:
        List of job dicts with ai_score and ai_reasoning populated,
        sorted by score descending, limited to top_n.

    Raises:
        NotImplementedError: This feature is not yet implemented.
    """
    raise NotImplementedError(
        "Phase 2: AI batch scoring not yet implemented. "
        "Will score all jobs and return the top matches."
    )
