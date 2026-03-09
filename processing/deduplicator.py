"""
processing/deduplicator.py — Deduplication logic for job results.

Identifies duplicate jobs by URL or by title+company match, merges data
from duplicates, and returns a deduplicated list.
"""

import logging
import re
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger(__name__)


def deduplicate(jobs: list[dict]) -> list[dict]:
    """
    Deduplicate a list of job dicts.

    Two jobs are considered duplicates if:
    - They have the same normalized job_url, OR
    - They have the same (title, company) pair after lowercasing/stripping

    When merging duplicates:
    - Keep the version with more complete data (longer description, has salary, etc.)
    - Combine the 'source' field (e.g., "indeed + google_dork")
    - Prefer ATS-direct sources over job board aggregators

    Args:
        jobs: List of job dicts (unified schema).

    Returns:
        Deduplicated list of job dicts.
    """
    if not jobs:
        return []

    logger.info("Deduplicating %d jobs...", len(jobs))

    # Track seen jobs by normalized URL and by (title, company) key
    url_index: dict[str, int] = {}  # normalized_url -> index in result
    title_company_index: dict[str, int] = {}  # "title|||company" -> index in result
    result: list[dict] = []

    for job in jobs:
        job_url = job.get("job_url", "") or ""
        title = (job.get("title") or "").lower().strip()
        company = (job.get("company") or "").lower().strip()

        normalized_url = _normalize_url(job_url)
        title_company_key = f"{title}|||{company}" if title and company else None

        # Check if duplicate by URL
        existing_idx = None
        if normalized_url and normalized_url in url_index:
            existing_idx = url_index[normalized_url]
        elif title_company_key and title_company_key in title_company_index:
            existing_idx = title_company_index[title_company_key]

        if existing_idx is not None:
            # Merge: keep the one with more data
            result[existing_idx] = _merge_jobs(result[existing_idx], job)
        else:
            # New job
            idx = len(result)
            result.append(job)
            if normalized_url:
                url_index[normalized_url] = idx
            if title_company_key:
                title_company_index[title_company_key] = idx

    removed = len(jobs) - len(result)
    logger.info("Deduplication complete: %d jobs → %d jobs (%d duplicates removed).",
                len(jobs), len(result), removed)
    return result


def _normalize_url(url: str) -> str:
    """
    Normalize a URL for comparison.

    Strips trailing slashes, query parameters, and fragments.
    Lowercases the scheme and host.
    """
    if not url:
        return ""

    url = url.strip()
    if not url.startswith("http"):
        return url.lower()

    try:
        parsed = urlparse(url)
        # Reconstruct without query and fragment
        normalized = urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            "",  # params
            "",  # query
            "",  # fragment
        ))
        return normalized
    except Exception:
        return url.lower().rstrip("/")


def _merge_jobs(existing: dict, new: dict) -> dict:
    """
    Merge two duplicate job dicts, keeping the most complete version.

    Strategy:
    1. Prefer ATS-direct source over job board (google_dork/greenhouse > indeed)
    2. Keep the one with more data overall
    3. Combine source fields
    4. Fill in None fields from the other version

    Args:
        existing: The previously stored job dict.
        new: The duplicate job dict.

    Returns:
        The merged job dict.
    """
    # Determine which is the "better" version
    existing_score = _data_completeness_score(existing)
    new_score = _data_completeness_score(new)

    # Prefer ATS-direct sources
    ats_sources = {"google_dork", "greenhouse", "lever", "workday", "ashby", "personio", "smartrecruiters"}
    existing_is_ats = (existing.get("source") or "") in ats_sources or existing.get("ats_platform")
    new_is_ats = (new.get("source") or "") in ats_sources or new.get("ats_platform")

    if new_is_ats and not existing_is_ats:
        primary, secondary = new, existing
    elif existing_is_ats and not new_is_ats:
        primary, secondary = existing, new
    elif new_score > existing_score:
        primary, secondary = new, existing
    else:
        primary, secondary = existing, new

    merged = dict(primary)

    # Combine sources
    sources = set()
    for src_field in [primary.get("source"), secondary.get("source")]:
        if src_field:
            for s in src_field.split(" + "):
                sources.add(s.strip())
    if sources:
        merged["source"] = " + ".join(sorted(sources))

    # Fill None fields from secondary
    for key, val in secondary.items():
        if merged.get(key) is None and val is not None:
            merged[key] = val

    # Keep longer description
    primary_desc = primary.get("description") or ""
    secondary_desc = secondary.get("description") or ""
    if len(secondary_desc) > len(primary_desc):
        merged["description"] = secondary_desc

    return merged


def _data_completeness_score(job: dict) -> int:
    """
    Calculate a completeness score for a job dict.

    Higher = more complete data.
    """
    score = 0
    if job.get("title"):
        score += 2
    if job.get("company"):
        score += 2
    if job.get("location"):
        score += 1
    if job.get("description"):
        score += 3
        # Bonus for longer descriptions
        desc_len = len(job["description"])
        if desc_len > 500:
            score += 2
        if desc_len > 2000:
            score += 2
    if job.get("date_posted"):
        score += 1
    if job.get("salary_min") is not None:
        score += 2
    if job.get("job_type"):
        score += 1
    if job.get("is_remote") is not None:
        score += 1
    if job.get("country"):
        score += 1
    if job.get("company_url"):
        score += 1
    return score
