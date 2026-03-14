"""
ai/resume_tailor.py — Gemini AI resume bullet tailoring.

Generates tailored resume bullet points optimized for specific job postings,
rewriting the user's experience to align with each job's requirements.
"""

import logging

import google.generativeai as genai

from ai.gemini_utils import generate_with_retry

logger = logging.getLogger(__name__)

RESUME_TAILOR_PROMPT = """\
You are an expert resume writer and career coach. Rewrite the CANDIDATE's resume bullet points \
to be perfectly tailored for the TARGET JOB below.

CANDIDATE PROFILE:
{profile}

TARGET JOB:
Title: {title}
Company: {company}
Location: {location}
Type: {job_type}
Remote: {is_remote}
Language requirement: {language}
Description:
{description}

INSTRUCTIONS:
- Rewrite 6-10 bullet points from the candidate's experience to align with THIS specific job.
- Use strong action verbs and quantify achievements where possible.
- Mirror keywords and phrases from the job description naturally.
- Focus on the most relevant experience — skip irrelevant roles/bullets.
- Each bullet should be 1-2 lines, starting with a past-tense action verb.
- Group bullets under the relevant role/position heading from the candidate's profile.
- Write in {output_language}.
- Format as plain text with clear section headers.

Output ONLY the tailored bullet points (no preamble, no explanation):
"""


def generate_tailored_bullets(
    job: dict,
    profile_text: str,
    model: genai.GenerativeModel,
    language: str | None = None,
) -> str:
    """Generate tailored resume bullet points for a specific job using Gemini AI.

    Args:
        job: A job dict (unified schema) with description.
        profile_text: The user's combined CV/profile text.
        model: Configured Gemini GenerativeModel instance.
        language: Language to write in. Defaults to the job's detected language.

    Returns:
        Formatted string of tailored resume bullet points, or an error message.
    """
    output_language = language or _infer_language(job)

    prompt = RESUME_TAILOR_PROMPT.format(
        profile=profile_text[:6000],
        title=job.get("title", "N/A"),
        company=job.get("company", "N/A"),
        location=job.get("location", "N/A"),
        job_type=job.get("job_type", "N/A"),
        is_remote="Yes" if job.get("is_remote") else "No",
        language=job.get("language", "N/A"),
        description=(job.get("description") or "No description available")[:4000],
        output_language=output_language,
    )

    bullets = generate_with_retry(model, prompt)
    if not bullets:
        return "Error: Gemini returned an empty or blocked response."
    return bullets


def _infer_language(job: dict) -> str:
    """Pick the output language based on the job's detected language field."""
    lang = (job.get("language") or "").lower()
    if "german" in lang:
        return "German"
    if "french" in lang:
        return "French"
    if "dutch" in lang:
        return "Dutch"
    if "spanish" in lang:
        return "Spanish"
    return "English"
