"""
processing/salary_estimator.py — AI-based salary estimation for jobs without salary data.

Uses Gemini to estimate a salary range based on title, company, location, and
description.  Populates ``salary_estimated_min`` and ``salary_estimated_max``
fields.  Estimated values are prefixed with "~" in the UI.
"""

import json
import logging
import time
from typing import Callable

import google.generativeai as genai

from config import GEMINI_RATE_LIMIT_DELAY, GEMINI_BATCH_SIZE
from ai.gemini_utils import generate_with_retry

logger = logging.getLogger(__name__)

ESTIMATION_PROMPT = """\
Estimate the annual salary range for each of the following jobs.
Use market data for the given location and role. If the location is in India,
return values in INR; for Europe use EUR; for USA/Canada use USD; otherwise
use the most likely local currency.

Return ONLY valid JSON — no markdown, no code fences — as an array:
[{{"job_index": 0, "currency": "USD", "min": 60000, "max": 90000}}, ...]

If you cannot estimate (too little information), return null for min and max.

JOBS:
{jobs_block}
"""


def estimate_salaries(
    jobs: list[dict],
    model: genai.GenerativeModel,
    batch_size: int = GEMINI_BATCH_SIZE,
    progress_callback: Callable[[str], None] | None = None,
) -> list[dict]:
    """Estimate salaries for jobs that don't have salary data.

    Only processes jobs where both ``salary_min`` and ``salary_max`` are None.
    Adds ``salary_estimated_min``, ``salary_estimated_max``, and
    ``salary_estimated_currency`` fields.

    Returns the same list of job dicts, mutated in place.
    """
    candidates = [
        (i, j) for i, j in enumerate(jobs)
        if not j.get("salary_min") and not j.get("salary_max")
    ]

    if not candidates:
        if progress_callback:
            progress_callback("Salary estimation: all jobs already have salary data.")
        return jobs

    total = len(candidates)
    if progress_callback:
        progress_callback(f"Salary estimation: {total} jobs need estimates...")

    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        batch = candidates[start:end]

        if progress_callback:
            progress_callback(f"Salary estimation: jobs {start + 1}-{end} of {total}")

        jobs_block = _build_jobs_block(batch)
        prompt = ESTIMATION_PROMPT.format(jobs_block=jobs_block)
        text = generate_with_retry(model, prompt)

        if text:
            parsed = _parse_response(text, len(batch))
            for bi, (orig_idx, _) in enumerate(batch):
                est = parsed[bi]
                if est:
                    jobs[orig_idx]["salary_estimated_min"] = est.get("min")
                    jobs[orig_idx]["salary_estimated_max"] = est.get("max")
                    jobs[orig_idx]["salary_estimated_currency"] = est.get("currency")
        else:
            for orig_idx, _ in batch:
                jobs[orig_idx].setdefault("salary_estimated_min", None)
                jobs[orig_idx].setdefault("salary_estimated_max", None)
                jobs[orig_idx].setdefault("salary_estimated_currency", None)

        time.sleep(GEMINI_RATE_LIMIT_DELAY)

    if progress_callback:
        progress_callback(f"Salary estimation: done — {total} jobs estimated.")

    return jobs


def _build_jobs_block(batch: list[tuple[int, dict]]) -> str:
    lines = []
    for bi, (_, job) in enumerate(batch):
        title = job.get("title") or "Untitled"
        company = job.get("company") or "Unknown"
        location = job.get("location") or "Unknown"
        country = job.get("country") or ""
        desc = (job.get("description") or "")[:1500]
        lines.append(
            f"--- JOB {bi} ---\n"
            f"Title: {title}\nCompany: {company}\n"
            f"Location: {location}, {country}\n"
            f"Description:\n{desc}\n"
        )
    return "\n".join(lines)


def _parse_response(text: str, batch_size: int) -> list[dict | None]:
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
                    sal_min = item.get("min")
                    sal_max = item.get("max")
                    if sal_min is not None or sal_max is not None:
                        result[idx] = {
                            "min": float(sal_min) if sal_min else None,
                            "max": float(sal_max) if sal_max else None,
                            "currency": item.get("currency", "USD"),
                        }
    except (json.JSONDecodeError, AttributeError, TypeError, ValueError):
        logger.debug("Failed to parse salary estimation response: %s", text[:200])

    return result
