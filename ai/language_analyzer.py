"""
ai/language_analyzer.py — Gemini-based language requirement analysis.

Uses AI to determine what language a job requires when regex-based detection
returns "unknown" or when the user wants higher-accuracy results.

Analyses the full job description to extract:
- What language the listing is written in
- What language(s) the job requires the candidate to speak
"""

import json
import logging
import time
from typing import Callable

import google.generativeai as genai

from config import GEMINI_RATE_LIMIT_DELAY, GEMINI_BATCH_SIZE
from ai.gemini_utils import generate_with_retry

logger = logging.getLogger(__name__)

LANGUAGE_PROMPT = """\
Analyse the following job listing and determine:
1. What language is the job description TEXT written in?
2. What language(s) does the job REQUIRE the candidate to speak/know?

Return ONLY valid JSON — no markdown, no code fences — in this exact format:
{{"listing_language": "<language name>", "language_required": "<language requirement>", "confidence": "<high|medium|low>"}}

Rules for language_required:
- If the job explicitly requires German (e.g. "German C1", "Deutschkenntnisse erforderlich"), return "German"
- If the job is in English and German is nice-to-have/optional, return "English (German plus)"
- If the job is in English with no German requirement, return "English"
- If the job requires French, return "French"
- If the job requires Hindi, return "Hindi"
- If the listing is in German but says English is the working language, return "English (German plus)"
- If you truly cannot determine, return "unknown"

Rules for listing_language:
- Return the language the description text is primarily written in
- Common values: "English", "German", "French", "Spanish", "Hindi", "Dutch"

JOB TITLE: {title}
COMPANY: {company}
LOCATION: {location}

DESCRIPTION:
{description}
"""

BATCH_PROMPT = """\
Analyse each job listing below and determine the language requirements.

Return ONLY valid JSON — no markdown, no code fences — as an array:
[{{"job_index": 0, "listing_language": "<lang>", "language_required": "<lang requirement>"}}, ...]

Rules for language_required:
- "German" if German is explicitly required
- "English (German plus)" if English job but German is nice-to-have
- "English" if English-only, no other language required
- "French", "Hindi", "Dutch", etc. for other requirements
- "unknown" if truly cannot determine

JOBS:
{jobs_block}
"""


def analyze_language_single(
    job: dict,
    model: genai.GenerativeModel,
) -> dict:
    """Analyse language requirements for a single job using AI.

    Returns a dict with keys: listing_language, language_required, confidence.
    """
    title = job.get("title") or ""
    company = job.get("company") or ""
    location = job.get("location") or ""
    desc = (job.get("description") or "")[:4000]

    if not desc.strip():
        return {"listing_language": "unknown", "language_required": "unknown", "confidence": "low"}

    prompt = LANGUAGE_PROMPT.format(
        title=title, company=company, location=location, description=desc,
    )
    text = generate_with_retry(model, prompt)
    if not text:
        return {"listing_language": "unknown", "language_required": "unknown", "confidence": "low"}

    return _parse_single_response(text)


def analyze_languages_batch(
    jobs: list[dict],
    model: genai.GenerativeModel,
    batch_size: int = GEMINI_BATCH_SIZE,
    progress_callback: Callable[[str], None] | None = None,
) -> list[dict]:
    """Analyse language requirements for ALL jobs using AI.

    Populates ``ai_detected_language`` on every job. Also back-fills
    ``listing_language`` and ``language_required`` when they are "unknown".

    Mutates the job dicts in place and returns the same list.
    """
    candidates = [
        (i, j) for i, j in enumerate(jobs)
        if not j.get("ai_detected_language")
    ]

    if not candidates:
        if progress_callback:
            progress_callback("AI Language Analysis: no jobs need analysis.")
        return jobs

    total = len(candidates)
    if progress_callback:
        progress_callback(f"AI Language Analysis: processing {total} jobs...")

    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        batch = candidates[start:end]

        if progress_callback:
            progress_callback(f"AI Language Analysis: jobs {start + 1}-{end} of {total}")

        jobs_block = _build_jobs_block(batch)
        prompt = BATCH_PROMPT.format(jobs_block=jobs_block)
        text = generate_with_retry(model, prompt)

        if text:
            parsed = _parse_batch_response(text, len(batch))
            for bi, (orig_idx, _) in enumerate(batch):
                result = parsed[bi]
                if result:
                    ai_req = result.get("language_required", "")
                    ai_listing = result.get("listing_language", "")

                    # Always store the AI's answer in the dedicated column
                    jobs[orig_idx]["ai_detected_language"] = ai_req or ai_listing or ""

                    # Back-fill listing_language / language_required only when unknown
                    if ai_listing and ai_listing != "unknown":
                        if (jobs[orig_idx].get("listing_language") or "unknown") == "unknown":
                            jobs[orig_idx]["listing_language"] = ai_listing
                    if ai_req and ai_req != "unknown":
                        if (jobs[orig_idx].get("language_required") or "unknown") == "unknown":
                            jobs[orig_idx]["language_required"] = ai_req
                            jobs[orig_idx]["language"] = ai_req

        time.sleep(GEMINI_RATE_LIMIT_DELAY)

    if progress_callback:
        progress_callback(f"AI Language Analysis: done — {total} jobs analysed.")

    return jobs


def _build_jobs_block(batch: list[tuple[int, dict]]) -> str:
    lines = []
    for bi, (_, job) in enumerate(batch):
        title = job.get("title") or "Untitled"
        company = job.get("company") or "Unknown"
        location = job.get("location") or "Unknown"
        desc = (job.get("description") or "")[:2500]
        lines.append(
            f"--- JOB {bi} ---\n"
            f"Title: {title}\nCompany: {company}\nLocation: {location}\n"
            f"Description:\n{desc}\n"
        )
    return "\n".join(lines)


def _parse_single_response(text: str) -> dict:
    fallback = {"listing_language": "unknown", "language_required": "unknown", "confidence": "low"}
    try:
        clean = text.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0]
        data = json.loads(clean)
        return {
            "listing_language": data.get("listing_language", "unknown"),
            "language_required": data.get("language_required", "unknown"),
            "confidence": data.get("confidence", "medium"),
        }
    except (json.JSONDecodeError, AttributeError, TypeError):
        logger.debug("Failed to parse AI language response: %s", text[:200])
        return fallback


def _parse_batch_response(text: str, batch_size: int) -> list[dict | None]:
    result: list[dict | None] = [None] * batch_size
    try:
        clean = text.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0]
        data = json.loads(clean)

        if isinstance(data, list):
            for item in data:
                idx = item.get("job_index", -1)
                if 0 <= idx < batch_size:
                    result[idx] = {
                        "listing_language": item.get("listing_language", "unknown"),
                        "language_required": item.get("language_required", "unknown"),
                    }
        elif isinstance(data, dict):
            result[0] = {
                "listing_language": data.get("listing_language", "unknown"),
                "language_required": data.get("language_required", "unknown"),
            }
    except (json.JSONDecodeError, AttributeError, TypeError):
        logger.debug("Failed to parse batch language response: %s", text[:200])

    return result
