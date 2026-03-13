"""ai package — Gemini-powered job scoring, cover letters, and profile loading."""

from ai.profile_loader import load_profile
from ai.scorer import score_job, score_jobs_batch
from ai.cover_letter import generate_cover_letter

__all__ = [
    "load_profile",
    "score_job",
    "score_jobs_batch",
    "generate_cover_letter",
]
