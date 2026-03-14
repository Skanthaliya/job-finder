"""
filtering/location_filter.py — Filter jobs by location (Country/Europe scope).
"""

import logging
from typing import Callable

from config import (
    GERMAN_CITIES,
    INDIAN_CITIES,
    ALLOWED_REMOTE_COUNTRIES,
    GLOBAL_REMOTE_KEYWORDS,
    BLOCKED_REMOTE_COUNTRIES,
)

logger = logging.getLogger(__name__)


def filter_by_location(
    jobs: list[dict],
    search_locations: list[str] | None,
    progress_callback: Callable[[str], None] | None = None,
) -> list[dict]:
    """Filter jobs to match the search location scope. Returns all jobs if no locations specified."""
    if not search_locations:
        return jobs

    pre_count = len(jobs)
    loc_filters = [loc.lower() for loc in search_locations]

    if "Germany" in search_locations or "germany" in loc_filters:
        loc_filters.extend(GERMAN_CITIES)
    if "India" in search_locations or "india" in loc_filters:
        loc_filters.extend(INDIAN_CITIES)

    filtered = []
    for j in jobs:
        job_loc = (j.get("location") or "").lower()
        job_title = (j.get("title") or "").lower()
        is_remote_flag = j.get("is_remote", False)

        is_remote_job = (
            is_remote_flag
            or "remote" in job_loc
            or "remote" in job_title
            or "home office" in job_loc
            or "wfh" in job_loc
        )

        if is_remote_job:
            if _is_blocked_remote(job_loc):
                logger.debug("Blocked remote: %s | %s", j.get("title", "?")[:40], job_loc[:40])
                continue

            is_global = any(kw in job_loc for kw in GLOBAL_REMOTE_KEYWORDS)
            is_allowed = any(c in job_loc for c in ALLOWED_REMOTE_COUNTRIES)
            is_no_location = len(job_loc.replace("remote", "").strip(" -,/")) < 3

            if is_global or is_allowed or is_no_location:
                filtered.append(j)
                continue

            filtered.append(j)
            continue

        if not job_loc or len(job_loc.strip()) < 2:
            filtered.append(j)
            continue

        if any(loc in job_loc for loc in loc_filters):
            filtered.append(j)
            continue

        if ", de" in job_loc or "germany" in job_loc or "deutschland" in job_loc:
            filtered.append(j)
            continue

        if ", in" in job_loc or "india" in job_loc or "bharat" in job_loc:
            if "India" in (search_locations or []) or "india" in loc_filters:
                filtered.append(j)
                continue

        if len(search_locations) > 1:
            filtered.append(j)
            continue

        logger.debug("Location filtered: %s | %s", j.get("title", "?")[:40], job_loc[:40])

    removed = pre_count - len(filtered)
    if removed > 0 and progress_callback:
        progress_callback(
            f"Location filter: removed {removed} jobs outside {search_locations[0]} "
            f"(kept valid remote + EU/India remote)"
        )

    return filtered


def _is_blocked_remote(job_loc: str) -> bool:
    """Check if a remote job is restricted to a blocked country."""
    return any(blocked in job_loc for blocked in BLOCKED_REMOTE_COUNTRIES)
