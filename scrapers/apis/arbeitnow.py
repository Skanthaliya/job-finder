"""
scrapers/apis/arbeitnow.py — Arbeitnow.com public API scraper.

Fetches jobs from https://www.arbeitnow.com/api/job-board-api and maps
them to the unified job schema with client-side filtering.
"""

import logging
import random
from typing import Callable

import requests

from config import USER_AGENTS, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

API_URL = "https://www.arbeitnow.com/api/job-board-api"


def scrape_arbeitnow(
    search_term: str = "",
    search_terms: list[str] | None = None,
    location: str = "",
    search_locations: list[str] | None = None,
    language_filter: str | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> list[dict]:
    """
    Scrape jobs from the Arbeitnow public API.

    Args:
        search_term: Keywords to filter by (legacy single-term).
        search_terms: List of job titles to search for (multi-role).
        location: Location to filter by.
        search_locations: List of locations to match against (country/Europe scope).
        language_filter: Optional language filter ("English", "German", etc.).
        progress_callback: Optional function for progress updates.

    Returns:
        List of dicts matching the unified job schema.
    """
    # Normalize search terms
    if search_terms:
        terms_list = search_terms
    elif search_term:
        terms_list = [search_term]
    else:
        terms_list = []
    search_terms_lower = [t.lower().strip() for t in terms_list if t.strip()]

    # Normalize location filters
    if search_locations:
        loc_filters = [loc.lower().strip() for loc in search_locations]
    elif location:
        loc_filters = [location.lower().strip()]
    else:
        loc_filters = []

    if progress_callback:
        progress_callback("Fetching jobs from Arbeitnow API...")

    jobs: list[dict] = []

    try:
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json",
        }

        all_postings: list[dict] = []
        page = 1
        max_pages = 5  # Limit to prevent excessive requests

        while page <= max_pages:
            url = f"{API_URL}?page={page}"
            logger.info("Fetching Arbeitnow page %d: %s", page, url)

            resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()

            postings = data.get("data", [])
            if not postings:
                break

            all_postings.extend(postings)

            # Check if there are more pages
            links = data.get("links", {})
            if not links.get("next"):
                break

            page += 1

        logger.info("Arbeitnow: Fetched %d total postings across %d pages.", len(all_postings), page)

        if progress_callback:
            progress_callback(f"Arbeitnow: {len(all_postings)} postings fetched. Filtering...")

        for posting in all_postings:
            try:
                title = posting.get("title", "") or ""
                company = posting.get("company_name", "") or ""
                loc = posting.get("location", "") or ""
                description = posting.get("description", "") or ""
                tags = posting.get("tags", []) or []
                tags_str = " ".join(tags).lower()

                # Strict multi-role keyword filter
                if search_terms_lower:
                    title_lower = title.lower()
                    searchable_lower = f"{title} {description} {tags_str}".lower()

                    term_match = False
                    for term in search_terms_lower:
                        # Full phrase match in title
                        if term in title_lower:
                            term_match = True
                            break
                        # All words must appear in title
                        words = term.split()
                        if all(w in title_lower for w in words):
                            term_match = True
                            break
                        # All words must appear in description/tags
                        if all(w in searchable_lower for w in words):
                            term_match = True
                            break

                    if not term_match:
                        continue

                # Location filter: match if ANY location filter matches
                if loc_filters:
                    loc_lower = loc.lower()
                    loc_match = any(lf in loc_lower for lf in loc_filters)
                    if not loc_match:
                        continue

                # Language filter via tags
                if language_filter and language_filter != "All":
                    if language_filter.lower() not in tags_str and language_filter.lower() not in description.lower():
                        pass  # Don't skip — language_detector will handle later

                # Parse remote status
                is_remote = posting.get("remote", False)
                if isinstance(is_remote, str):
                    is_remote = is_remote.lower() in ("true", "yes", "1")

                # Parse date — Arbeitnow returns Unix timestamps
                date_posted = posting.get("created_at")
                if date_posted is not None:
                    if isinstance(date_posted, (int, float)):
                        try:
                            from datetime import datetime as dt
                            date_posted = dt.fromtimestamp(int(date_posted)).strftime("%Y-%m-%d")
                        except (ValueError, OSError, OverflowError):
                            date_posted = None
                    elif isinstance(date_posted, str):
                        if date_posted.strip().isdigit() and len(date_posted.strip()) >= 10:
                            try:
                                from datetime import datetime as dt
                                date_posted = dt.fromtimestamp(int(date_posted[:10])).strftime("%Y-%m-%d")
                            except (ValueError, OSError, OverflowError):
                                date_posted = None
                        else:
                            date_posted = date_posted[:10]  # Already ISO format

                # Build job URL
                job_url = posting.get("url") or posting.get("slug", "")
                if job_url and not job_url.startswith("http"):
                    job_url = f"https://www.arbeitnow.com/view/{job_url}"

                job = {
                    "source": "arbeitnow",
                    "ats_platform": None,
                    "title": title,
                    "company": company,
                    "location": loc,
                    "country": None,
                    "date_posted": date_posted,
                    "job_type": _parse_job_type(tags),
                    "is_remote": bool(is_remote),
                    "salary_min": None,
                    "salary_max": None,
                    "salary_currency": None,
                    "salary_interval": None,
                    "job_url": job_url,
                    "company_url": None,
                    "description": description,
                    "language": None,
                    "ai_score": None,
                    "ai_reasoning": None,
                    "ai_cover_letter": None,
                    "ai_resume_bullets": None,
                }

                if job["job_url"]:
                    jobs.append(job)

            except Exception as e:
                logger.warning("Error parsing Arbeitnow posting: %s", e)
                continue

        logger.info("Arbeitnow: %d jobs after filtering.", len(jobs))
        if progress_callback:
            progress_callback(f"Arbeitnow: {len(jobs)} jobs matched filters.")

    except requests.exceptions.RequestException as e:
        logger.error("Arbeitnow API request failed: %s", e)
        if progress_callback:
            progress_callback(f"Arbeitnow error: {e}")
    except Exception as e:
        logger.error("Arbeitnow scraper failed: %s", e, exc_info=True)
        if progress_callback:
            progress_callback(f"Arbeitnow error: {e}")

    return jobs


def _parse_job_type(tags: list) -> str | None:
    """Extract job type from Arbeitnow tags list."""
    tags_lower = [t.lower() for t in tags] if tags else []
    if "full-time" in tags_lower or "full time" in tags_lower or "fulltime" in tags_lower:
        return "fulltime"
    if "part-time" in tags_lower or "part time" in tags_lower or "parttime" in tags_lower:
        return "parttime"
    if "contract" in tags_lower or "freelance" in tags_lower:
        return "contract"
    if "internship" in tags_lower or "intern" in tags_lower:
        return "internship"
    return None
