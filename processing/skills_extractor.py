"""
processing/skills_extractor.py — Extract structured skills from job descriptions using Gemini.

Populates a ``skills`` field (list of strings) on each job dict, enabling
skills-based matching and gap analysis in the AI scorer.
"""

import json
import logging
import time
from typing import Callable

import google.generativeai as genai

from config import GEMINI_RATE_LIMIT_DELAY, GEMINI_BATCH_SIZE
from ai.gemini_utils import generate_with_retry

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """\
Extract a flat list of technical and professional skills from the following job description.
Return ONLY valid JSON — no markdown, no code fences — in this exact format:
{{"skills": ["skill1", "skill2", ...]}}

Rules:
- Include programming languages, frameworks, tools, methodologies, soft skills, and domain knowledge.
- Normalise names (e.g. "JS" → "JavaScript", "k8s" → "Kubernetes").
- Maximum 25 skills per job.
- If the description is empty or uninformative, return {{"skills": []}}.

JOB TITLE: {title}
DESCRIPTION:
{description}
"""

BATCH_PROMPT = """\
Extract skills from each of the following job descriptions.
Return ONLY valid JSON — no markdown, no code fences — as an array of objects:
[{{"job_index": 0, "skills": ["skill1", ...]}}, ...]

Rules:
- Include programming languages, frameworks, tools, methodologies, soft skills, and domain knowledge.
- Normalise names (e.g. "JS" → "JavaScript", "k8s" → "Kubernetes").
- Maximum 25 skills per job.
- If a description is empty, return an empty skills list for that index.

JOBS:
{jobs_block}
"""


def extract_skills_single(
    job: dict,
    model: genai.GenerativeModel,
) -> list[str]:
    """Extract skills from a single job's description."""
    title = job.get("title") or ""
    desc = (job.get("description") or "")[:4000]

    if not desc.strip():
        return []

    prompt = EXTRACTION_PROMPT.format(title=title, description=desc)
    text = generate_with_retry(model, prompt)
    if not text:
        return []

    return _parse_skills_response(text)


def extract_skills_batch(
    jobs: list[dict],
    model: genai.GenerativeModel,
    batch_size: int = GEMINI_BATCH_SIZE,
    progress_callback: Callable[[str], None] | None = None,
) -> list[dict]:
    """Extract skills for a list of jobs, adding a ``skills`` field to each.

    Returns the same list of job dicts, mutated in place with the new field.
    """
    total = len(jobs)
    if progress_callback:
        progress_callback(f"Skills extraction: processing {total} jobs...")

    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        batch = jobs[start:end]

        if progress_callback:
            progress_callback(f"Skills extraction: jobs {start + 1}-{end} of {total}")

        jobs_block = _build_jobs_block(batch, start)
        prompt = BATCH_PROMPT.format(jobs_block=jobs_block)
        text = generate_with_retry(model, prompt)

        if text:
            parsed = _parse_batch_response(text, len(batch))
            for i, skills in enumerate(parsed):
                jobs[start + i]["skills"] = skills
        else:
            for i in range(len(batch)):
                jobs[start + i].setdefault("skills", [])

        time.sleep(GEMINI_RATE_LIMIT_DELAY)

    if progress_callback:
        progress_callback(f"Skills extraction: done — {total} jobs processed.")

    return jobs


def _build_jobs_block(batch: list[dict], offset: int) -> str:
    lines = []
    for i, job in enumerate(batch):
        title = job.get("title") or "Untitled"
        desc = (job.get("description") or "")[:3000]
        lines.append(f"--- JOB {offset + i} ---\nTitle: {title}\nDescription:\n{desc}\n")
    return "\n".join(lines)


def _parse_skills_response(text: str) -> list[str]:
    """Parse a single-job skills extraction response."""
    try:
        clean = text.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0]
        data = json.loads(clean)
        skills = data.get("skills", [])
        return [str(s).strip() for s in skills if s][:25]
    except (json.JSONDecodeError, AttributeError, TypeError):
        logger.debug("Failed to parse skills response: %s", text[:200])
        return []


def _parse_batch_response(text: str, batch_size: int) -> list[list[str]]:
    """Parse a batch skills extraction response."""
    result: list[list[str]] = [[] for _ in range(batch_size)]
    try:
        clean = text.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0]
        data = json.loads(clean)

        if isinstance(data, list):
            for item in data:
                idx = item.get("job_index", -1)
                skills = item.get("skills", [])
                if 0 <= idx < batch_size:
                    result[idx] = [str(s).strip() for s in skills if s][:25]
        elif isinstance(data, dict) and "skills" in data:
            result[0] = [str(s).strip() for s in data["skills"] if s][:25]
    except (json.JSONDecodeError, AttributeError, TypeError):
        logger.debug("Failed to parse batch skills response: %s", text[:200])

    return result
