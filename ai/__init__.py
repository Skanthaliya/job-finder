"""ai package — Gemini-powered job scoring, cover letters, resume tailoring, and profile loading."""

from ai.profile_loader import load_profile
from ai.scorer import score_job, score_jobs_batch
from ai.cover_letter import generate_cover_letter
from ai.resume_tailor import generate_tailored_bullets

__all__ = [
    "load_profile",
    "score_job",
    "score_jobs_batch",
    "generate_cover_letter",
    "generate_tailored_bullets",
]
