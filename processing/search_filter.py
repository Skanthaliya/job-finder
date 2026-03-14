"""
processing/search_filter.py — Shared search-term and location filtering for jobs.

Centralises the "does this job match the search query?" logic that was
previously duplicated across greenhouse.py, lever.py, ashby.py, personio.py,
ats_discovery.py, career_page_crawler.py, arbeitnow.py, and remotive.py.
"""


def matches_search_term(
    job: dict,
    search_term: str,
) -> bool:
    """Return True if any word from *search_term* appears in the job's title or description.

    This is a loose "any-word" match — the same logic the ATS scrapers used.
    """
    if not search_term:
        return True

    search_words = search_term.lower().split()
    title = (job.get("title") or "").lower()
    desc = (job.get("description") or "").lower()

    return any(w in title or w in desc for w in search_words)


def matches_search_terms_strict(
    job: dict,
    search_terms: list[str],
) -> bool:
    """Return True if *all* words of at least one search term appear in title or description.

    This is the stricter "all-words" match used by career_page_crawler and ats_discovery.
    """
    if not search_terms:
        return True

    title = (job.get("title") or "").lower()
    desc = (job.get("description") or "").lower()

    for term in search_terms:
        words = term.lower().split()
        if all(w in title for w in words) or all(w in desc for w in words):
            return True

    return False


def matches_location(
    job: dict,
    location: str,
) -> bool:
    """Return True if *location* appears in the job's location string."""
    if not location:
        return True

    job_loc = (job.get("location") or "").lower()
    return location.lower() in job_loc


def filter_jobs(
    jobs: list[dict],
    search_term: str | None = None,
    search_terms: list[str] | None = None,
    location: str | None = None,
    strict: bool = False,
) -> list[dict]:
    """Filter a list of jobs by search term(s) and location.

    Args:
        jobs: List of job dicts.
        search_term: Single search string (any-word match).
        search_terms: Multiple search strings (all-words-of-any-term match when strict=True).
        location: Location string to match.
        strict: If True, use all-words matching; otherwise any-word.

    Returns:
        Filtered list of job dicts.
    """
    result = []
    for job in jobs:
        if strict and search_terms:
            if not matches_search_terms_strict(job, search_terms):
                continue
        elif search_term:
            if not matches_search_term(job, search_term):
                continue

        if location and not matches_location(job, location):
            continue

        result.append(job)

    return result
