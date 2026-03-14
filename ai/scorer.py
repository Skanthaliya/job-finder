"""
ai/scorer.py — Gemini AI job scoring.

Scores job postings against the user's CV/profile text using the
Google Gemini API.  Returns a relevance score (1-100), reasoning,
pros, and cons for each job.
"""

import json
import logging
import re
import time
from typing import Callable

import google.generativeai as genai

from config import GEMINI_RATE_LIMIT_DELAY, GEMINI_BATCH_SIZE
from ai.gemini_utils import generate_with_retry

logger = logging.getLogger(__name__)

SCORING_PROMPT = """\
You are a career advisor AI. Score how well the CANDIDATE matches the JOB below.

CANDIDATE PROFILE:
{profile}

JOB:
Title: {title}
Company: {company}
Location: {location}
Type: {job_type}
Remote: {is_remote}
Listing written in: {listing_language}
Language required to speak: {language_required}
Experience level: {experience_level}
Salary: {salary}
Description:
{description}

SCORING RUBRIC (weight each area):
- Skills match (35%): Do the candidate's skills align with the job requirements?
- Experience level (20%): Is the candidate's seniority appropriate?
- Location & remote fit (15%): Can the candidate work from the required location?
- Language fit (15%): Does the candidate speak the required language(s)?
- Overall role alignment (15%): Does the job title/domain match the candidate's career?

Return ONLY valid JSON (no markdown, no code fences) in this exact format:
{{"score": <int 1-100>, "reasoning": "<2-3 sentence summary>", "pros": ["<pro1>", "<pro2>"], "cons": ["<con1>", "<con2>"]}}
"""

BATCH_PROMPT = """\
You are a career advisor AI. Score how well the CANDIDATE matches each JOB below.

CANDIDATE PROFILE:
{profile}

JOBS:
{jobs_block}

SCORING RUBRIC (weight each area):
- Skills match (35%): Do the candidate's skills align with the job requirements?
- Experience level (20%): Is the candidate's seniority appropriate?
- Location & remote fit (15%): Can the candidate work from the required location?
- Language fit (15%): Does the candidate speak the required language(s)?
- Overall role alignment (15%): Does the job title/domain match the candidate's career?

Return ONLY a valid JSON array (no markdown, no code fences). One object per job, in the SAME order:
[{{"job_index": 0, "score": <int 1-100>, "reasoning": "<2-3 sentences>", "pros": ["..."], "cons": ["..."]}}, ...]
"""


def _format_salary(job: dict) -> str:
    sal_min = job.get("salary_min")
    sal_max = job.get("salary_max")
    currency = job.get("salary_currency", "")
    if sal_min and sal_max:
        return f"{currency} {sal_min:,.0f} - {sal_max:,.0f}"
    if sal_min:
        return f"{currency} {sal_min:,.0f}+"
    return "Not specified"


def _format_job_for_prompt(job: dict, index: int | None = None) -> str:
    prefix = f"[JOB {index}]\n" if index is not None else ""
    desc = (job.get("description") or "")[:3000]
    return (
        f"{prefix}"
        f"Title: {job.get('title', 'N/A')}\n"
        f"Company: {job.get('company', 'N/A')}\n"
        f"Location: {job.get('location', 'N/A')}\n"
        f"Type: {job.get('job_type', 'N/A')}\n"
        f"Remote: {job.get('is_remote', 'N/A')}\n"
        f"Listing written in: {job.get('listing_language', 'N/A')}\n"
        f"Language required: {job.get('language_required') or job.get('language', 'N/A')}\n"
        f"Experience: {job.get('experience_level', 'N/A')}\n"
        f"Salary: {_format_salary(job)}\n"
        f"Description:\n{desc}\n"
    )


def _parse_json_response(text: str) -> dict | list | None:
    """Extract JSON from Gemini response, stripping markdown fences if present."""
    text = text.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence_match:
        text = fence_match.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        json_match = re.search(r"[\[{][\s\S]*[\]}]", text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
    logger.warning("Failed to parse Gemini JSON response: %s", text[:200])
    return None


def score_job(job: dict, profile_text: str, model: genai.GenerativeModel) -> dict:
    """Score a single job against the user's profile.

    Returns:
        Dict with keys: score (int), reasoning (str), pros (list), cons (list).
    """
    prompt = SCORING_PROMPT.format(
        profile=profile_text[:6000],
        title=job.get("title", "N/A"),
        company=job.get("company", "N/A"),
        location=job.get("location", "N/A"),
        job_type=job.get("job_type", "N/A"),
        is_remote=job.get("is_remote", "N/A"),
        listing_language=job.get("listing_language", "N/A"),
        language_required=job.get("language_required") or job.get("language", "N/A"),
        experience_level=job.get("experience_level", "N/A"),
        salary=_format_salary(job),
        description=(job.get("description") or "")[:3000],
    )

    text = generate_with_retry(model, prompt)
    if not text:
        return {"score": 0, "reasoning": "Gemini returned no usable response", "pros": [], "cons": []}

    parsed = _parse_json_response(text)

    if isinstance(parsed, dict) and "score" in parsed:
        return {
            "score": max(1, min(100, int(parsed["score"]))),
            "reasoning": parsed.get("reasoning", ""),
            "pros": parsed.get("pros", []),
            "cons": parsed.get("cons", []),
        }

    return {"score": 0, "reasoning": "Failed to parse AI response", "pros": [], "cons": []}


def score_jobs_batch(
    jobs: list[dict],
    profile_text: str,
    model: genai.GenerativeModel,
    progress_callback: Callable[[str], None] | None = None,
) -> list[dict]:
    """Score all jobs in batches and populate ai_score / ai_reasoning fields.

    Returns the same list of jobs, now with ai_score and ai_reasoning set,
    sorted by score descending.
    """
    total = len(jobs)
    scored = 0
    batch_size = GEMINI_BATCH_SIZE

    for batch_start in range(0, total, batch_size):
        batch = jobs[batch_start : batch_start + batch_size]

        if progress_callback:
            progress_callback(f"Scoring jobs {batch_start + 1}-{min(batch_start + batch_size, total)} of {total}...")

        try:
            results = _score_batch(batch, profile_text, model)
            for i, result in enumerate(results):
                idx = batch_start + i
                if idx < total:
                    jobs[idx]["ai_score"] = result.get("score", 0)
                    reasoning = result.get("reasoning", "")
                    pros = result.get("pros", [])
                    cons = result.get("cons", [])
                    jobs[idx]["ai_pros"] = pros
                    jobs[idx]["ai_cons"] = cons
                    full_reasoning = reasoning
                    if pros:
                        full_reasoning += "\nPros: " + "; ".join(pros)
                    if cons:
                        full_reasoning += "\nCons: " + "; ".join(cons)
                    jobs[idx]["ai_reasoning"] = full_reasoning
                    scored += 1
        except Exception as e:
            logger.error("Batch scoring failed at %d: %s", batch_start, e)
            for i in range(len(batch)):
                idx = batch_start + i
                if idx < total:
                    jobs[idx]["ai_score"] = 0
                    jobs[idx]["ai_reasoning"] = f"Scoring failed: {e}"
                    jobs[idx]["ai_pros"] = []
                    jobs[idx]["ai_cons"] = []
                    scored += 1

        if batch_start + batch_size < total:
            time.sleep(GEMINI_RATE_LIMIT_DELAY)

    jobs.sort(key=lambda j: j.get("ai_score") or 0, reverse=True)

    if progress_callback:
        progress_callback(f"Scoring complete! {scored}/{total} jobs scored.")

    return jobs


def _score_batch(
    batch: list[dict],
    profile_text: str,
    model: genai.GenerativeModel,
) -> list[dict]:
    """Score a small batch of jobs in a single Gemini call."""
    if len(batch) == 1:
        result = score_job(batch[0], profile_text, model)
        return [result]

    jobs_block = "\n---\n".join(
        _format_job_for_prompt(job, index=i) for i, job in enumerate(batch)
    )

    prompt = BATCH_PROMPT.format(
        profile=profile_text[:6000],
        jobs_block=jobs_block,
    )

    text = generate_with_retry(model, prompt)
    if not text:
        logger.warning("Batch scoring got no response, falling back to single scoring")
        results = []
        for job in batch:
            try:
                result = score_job(job, profile_text, model)
                results.append(result)
                time.sleep(GEMINI_RATE_LIMIT_DELAY)
            except Exception as e:
                logger.error("Single score fallback failed: %s", e)
                results.append({"score": 0, "reasoning": f"Error: {e}", "pros": [], "cons": []})
        return results

    parsed = _parse_json_response(text)

    if isinstance(parsed, list):
        results = []
        for item in parsed:
            results.append({
                "score": max(1, min(100, int(item.get("score", 0)))),
                "reasoning": item.get("reasoning", ""),
                "pros": item.get("pros", []),
                "cons": item.get("cons", []),
            })
        while len(results) < len(batch):
            results.append({"score": 0, "reasoning": "Missing from batch response", "pros": [], "cons": []})
        return results

    logger.warning("Batch response was not a list, falling back to single scoring")
    results = []
    for job in batch:
        try:
            result = score_job(job, profile_text, model)
            results.append(result)
            time.sleep(GEMINI_RATE_LIMIT_DELAY)
        except Exception as e:
            logger.error("Single score fallback failed: %s", e)
            results.append({"score": 0, "reasoning": f"Error: {e}", "pros": [], "cons": []})
    return results
