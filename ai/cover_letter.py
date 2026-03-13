"""
ai/cover_letter.py — Gemini AI cover letter generation.

Generates tailored cover letters for specific job postings based on
the user's CV/profile text, written in the appropriate language.

The prompt is loaded from cover_letter_prompt.txt so you can customize
your instructions without touching code. If the file is missing or empty,
a sensible default is used.
"""

import logging
import os

import google.generativeai as genai

from config import COVER_LETTER_PROMPT_PATH

logger = logging.getLogger(__name__)

DEFAULT_PROMPT = """\
You are a professional career consultant. Write a tailored cover letter for the CANDIDATE applying to the JOB below.

CANDIDATE PROFILE:
{profile}

JOB DETAILS:
Title: {title}
Company: {company}
Location: {location}
Type: {job_type}
Remote: {is_remote}
Language requirement: {language}
Description:
{description}

INSTRUCTIONS:
- Write the cover letter in {output_language}.
- Use a professional but warm tone.
- Highlight the candidate's most relevant skills and experience for THIS specific job.
- Reference specific requirements from the job description.
- Keep it concise: 3-4 paragraphs, roughly 250-350 words.
- Do NOT include placeholder brackets like [Your Name] — use the candidate's actual details from the profile.
- Do NOT include a subject line or email headers — just the letter body.
- Start with "Dear Hiring Manager," (or equivalent in the target language).
- End with a professional closing.

Write the cover letter now:
"""


def _load_prompt_template() -> str:
    """Load the cover letter prompt from the external file, or fall back to default."""
    if os.path.exists(COVER_LETTER_PROMPT_PATH):
        try:
            with open(COVER_LETTER_PROMPT_PATH, "r", encoding="utf-8") as f:
                text = f.read().strip()
            if text:
                logger.info("Loaded custom cover letter prompt from %s", COVER_LETTER_PROMPT_PATH)
                return text
        except Exception as e:
            logger.warning("Failed to read %s: %s — using default prompt", COVER_LETTER_PROMPT_PATH, e)
    return DEFAULT_PROMPT


def generate_cover_letter(
    job: dict,
    profile_text: str,
    model: genai.GenerativeModel,
    language: str | None = None,
) -> str:
    """Generate a tailored cover letter for a specific job.

    Args:
        job: A job dict (unified schema) with description.
        profile_text: The user's combined CV/profile text.
        model: Configured Gemini GenerativeModel instance.
        language: Language to write in. Defaults to the job's detected language.

    Returns:
        Generated cover letter text, or an error message string.
    """
    output_language = language or _infer_language(job)
    template = _load_prompt_template()

    prompt = template.format(
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

    try:
        response = model.generate_content(prompt)
        letter = response.text.strip()
        if not letter:
            return "Error: Gemini returned an empty response."
        return letter
    except Exception as e:
        logger.error("Cover letter generation failed: %s", e)
        return f"Error generating cover letter: {e}"


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
