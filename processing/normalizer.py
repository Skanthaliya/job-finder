"""
processing/normalizer.py — Normalize all job data to the unified schema.

Ensures every job dict has ALL required fields, strips whitespace,
normalizes dates, locations, and job types.
"""

import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

# Canonical field list for the unified schema
UNIFIED_SCHEMA_FIELDS = [
    "source",
    "ats_platform",
    "title",
    "company",
    "location",
    "country",
    "date_posted",
    "job_type",
    "is_remote",
    "salary_min",
    "salary_max",
    "salary_currency",
    "salary_interval",
    "job_url",
    "company_url",
    "description",
    "language",
    "ai_score",
    "ai_reasoning",
    "ai_cover_letter",
    "ai_resume_bullets",
]

# Valid job types
VALID_JOB_TYPES = {"fulltime", "parttime", "contract", "internship"}

# Job type normalization mappings
JOB_TYPE_MAP = {
    "full-time": "fulltime",
    "full time": "fulltime",
    "ft": "fulltime",
    "permanent": "fulltime",
    "part-time": "parttime",
    "part time": "parttime",
    "pt": "parttime",
    "freelance": "contract",
    "contractor": "contract",
    "temporary": "contract",
    "temp": "contract",
    "intern": "internship",
    "internships": "internship",
    "working student": "internship",
    "werkstudent": "internship",
}


def normalize_jobs(jobs: list[dict]) -> list[dict]:
    """
    Normalize a list of job dicts to ensure consistency with the unified schema.

    - Fills missing fields with None
    - Strips whitespace from strings
    - Normalizes location (title case)
    - Normalizes date_posted to ISO format
    - Normalizes job_type to lowercase canonical form

    Args:
        jobs: List of raw job dicts (potentially with missing or inconsistent fields).

    Returns:
        List of cleaned, normalized job dicts.
    """
    normalized = []
    for i, job in enumerate(jobs):
        try:
            clean = _normalize_single(job)
            normalized.append(clean)
        except Exception as e:
            logger.warning("Error normalizing job %d: %s", i, e)
            # Still try to include it with whatever data we have
            fallback = {field: job.get(field) for field in UNIFIED_SCHEMA_FIELDS}
            normalized.append(fallback)

    logger.info("Normalized %d jobs.", len(normalized))
    return normalized


def _normalize_single(job: dict) -> dict:
    """Normalize a single job dict."""
    clean: dict = {}

    for field in UNIFIED_SCHEMA_FIELDS:
        clean[field] = job.get(field)

    # Strip whitespace from string fields
    for field in ["source", "ats_platform", "title", "company", "location",
                  "country", "job_url", "company_url", "salary_currency",
                  "salary_interval"]:
        if clean[field] and isinstance(clean[field], str):
            clean[field] = clean[field].strip()

    # Normalize title — strip extra whitespace
    if clean["title"]:
        clean["title"] = re.sub(r"\s+", " ", clean["title"]).strip()

    # Normalize company — strip extra whitespace
    if clean["company"]:
        clean["company"] = re.sub(r"\s+", " ", clean["company"]).strip()

    # Normalize location — trim, title case
    if clean["location"]:
        clean["location"] = re.sub(r"\s+", " ", clean["location"]).strip()
        # Only title-case if it's not already mixed case (to preserve things like "USA")
        if clean["location"] == clean["location"].lower():
            clean["location"] = clean["location"].title()

    # Normalize country
    if clean["country"] and isinstance(clean["country"], str):
        clean["country"] = clean["country"].strip().title()

    # Normalize date_posted to ISO format YYYY-MM-DD
    clean["date_posted"] = _normalize_date(clean["date_posted"])

    # Normalize job_type to canonical lowercase
    clean["job_type"] = _normalize_job_type(clean["job_type"])

    # Normalize is_remote to bool or None
    if clean["is_remote"] is not None:
        clean["is_remote"] = bool(clean["is_remote"])

    # Normalize salary fields to float or None
    for sal_field in ["salary_min", "salary_max"]:
        if clean[sal_field] is not None:
            try:
                clean[sal_field] = float(clean[sal_field])
            except (ValueError, TypeError):
                clean[sal_field] = None

    # Normalize salary_currency to uppercase
    if clean["salary_currency"]:
        clean["salary_currency"] = clean["salary_currency"].upper().strip()

    # Normalize salary_interval to lowercase
    if clean["salary_interval"]:
        clean["salary_interval"] = clean["salary_interval"].lower().strip()

    # Normalize job_url — strip whitespace
    if clean["job_url"]:
        clean["job_url"] = clean["job_url"].strip()

    # Normalize source — lowercase
    if clean["source"]:
        clean["source"] = clean["source"].lower().strip()

    # Normalize ats_platform — lowercase
    if clean["ats_platform"]:
        clean["ats_platform"] = clean["ats_platform"].lower().strip()

    return clean


def _normalize_date(date_val) -> str | None:
    """
    Normalize a date value to ISO format string YYYY-MM-DD.

    Handles strings, datetime objects, and various date formats.
    """
    if date_val is None:
        return None

    if isinstance(date_val, datetime):
        return date_val.strftime("%Y-%m-%d")

    if not isinstance(date_val, str):
        try:
            return str(date_val)[:10]
        except Exception:
            return None

    date_str = date_val.strip()
    if not date_str:
        return None

    # Already ISO format
    if re.match(r"^\d{4}-\d{2}-\d{2}", date_str):
        return date_str[:10]

    # Try common formats
    formats = [
        "%Y-%m-%dT%H:%M:%S",  # ISO with time
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d.%m.%Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str[:len(date_str)], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Fallback: return first 10 chars if they look like a date
    if len(date_str) >= 10 and date_str[:4].isdigit():
        return date_str[:10]

    logger.debug("Could not parse date: %s", date_str)
    return date_str  # Return as-is rather than losing data


def _normalize_job_type(job_type) -> str | None:
    """Normalize job_type to one of the canonical types or None."""
    if job_type is None:
        return None

    if not isinstance(job_type, str):
        job_type = str(job_type)

    jt = job_type.lower().strip()

    if jt in VALID_JOB_TYPES:
        return jt

    if jt in JOB_TYPE_MAP:
        return JOB_TYPE_MAP[jt]

    # Partial match
    for key, val in JOB_TYPE_MAP.items():
        if key in jt:
            return val

    return jt  # Return as-is if unrecognized
