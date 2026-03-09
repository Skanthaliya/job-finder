"""
scrapers/apis/remotive.py — Remotive.com public API scraper.

Fetches remote jobs from https://remotive.com/api/remote-jobs and maps
them to the unified job schema with client-side filtering.
"""

import logging
import random
from typing import Callable

import requests

from config import USER_AGENTS, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

API_URL = "https://remotive.com/api/remote-jobs"

# Category slug mappings for Remotive API
CATEGORY_MAP = {
    "software": "software-dev",
    "engineer": "software-dev",
    "developer": "software-dev",
    "data": "data",
    "design": "design",
    "product": "product",
    "marketing": "marketing",
    "sales": "sales",
    "customer": "customer-support",
    "devops": "devops",
    "qa": "qa",
    "writing": "writing",
    "finance": "finance",
    "hr": "hr",
    "legal": "legal",
}


def scrape_remotive(
    search_term: str = "",
    search_terms: list[str] | None = None,
    location: str = "",
    search_locations: list[str] | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> list[dict]:
    """
    Scrape remote jobs from the Remotive public API.

    Args:
        search_term: Keywords to filter by (legacy single-term).
        search_terms: List of job titles for multi-role search.
        location: Location to filter by (many Remotive jobs are worldwide).
        search_locations: List of locations to match against.
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

    # Use first term for category mapping
    search_lower = search_terms_lower[0] if search_terms_lower else ""

    # Normalize location filters
    if search_locations:
        loc_filters = [loc.lower().strip() for loc in search_locations]
    elif location:
        loc_filters = [location.lower().strip()]
    else:
        loc_filters = []
    if progress_callback:
        progress_callback("Fetching jobs from Remotive API...")

    jobs: list[dict] = []

    try:
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json",
        }

        # Try to map search_term to a Remotive category
        params = {}
        for keyword, category in CATEGORY_MAP.items():
            if keyword in search_lower:
                params["category"] = category
                break

        logger.info("Fetching Remotive jobs with params: %s", params)
        resp = requests.get(API_URL, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        all_jobs = data.get("jobs", [])
        logger.info("Remotive: Fetched %d total jobs.", len(all_jobs))

        if progress_callback:
            progress_callback(f"Remotive: {len(all_jobs)} jobs fetched. Filtering...")

        for posting in all_jobs:
            try:
                title = posting.get("title", "") or ""
                company = posting.get("company_name", "") or ""
                candidate_location = posting.get("candidate_required_location", "") or ""
                description = posting.get("description", "") or ""
                category = posting.get("category", "") or ""
                job_type = posting.get("job_type", "") or ""
                pub_date = posting.get("publication_date") or ""
                url = posting.get("url", "") or ""

                # Strict multi-role keyword filter
                if search_terms_lower:
                    title_lower = title.lower()
                    searchable = f"{title} {description} {category}".lower()

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
                        # All words must appear in description
                        if all(w in searchable for w in words):
                            term_match = True
                            break

                    if not term_match:
                        continue

                # Location filter
                if loc_filters:
                    loc_searchable = candidate_location.lower()
                    loc_match = any(lf in loc_searchable for lf in loc_filters)
                    if not loc_match and "worldwide" not in loc_searchable:
                        continue

                # Parse date
                date_posted = None
                if pub_date:
                    try:
                        date_posted = pub_date[:10]  # ISO format
                    except Exception:
                        date_posted = None

                # Parse job_type
                parsed_type = _parse_job_type(job_type)

                # Build salary info from salary string
                salary = posting.get("salary", "") or ""
                salary_min, salary_max, salary_currency = _parse_salary(salary)

                job = {
                    "source": "remotive",
                    "ats_platform": None,
                    "title": title,
                    "company": company,
                    "location": candidate_location or "Remote",
                    "country": None,
                    "date_posted": date_posted,
                    "job_type": parsed_type,
                    "is_remote": True,  # All Remotive jobs are remote
                    "salary_min": salary_min,
                    "salary_max": salary_max,
                    "salary_currency": salary_currency,
                    "salary_interval": "yearly" if salary_min else None,
                    "job_url": url,
                    "company_url": posting.get("company_logo_url"),
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
                logger.warning("Error parsing Remotive posting: %s", e)
                continue

        logger.info("Remotive: %d jobs after filtering.", len(jobs))
        if progress_callback:
            progress_callback(f"Remotive: {len(jobs)} jobs matched filters.")

    except requests.exceptions.RequestException as e:
        logger.error("Remotive API request failed: %s", e)
        if progress_callback:
            progress_callback(f"Remotive error: {e}")
    except Exception as e:
        logger.error("Remotive scraper failed: %s", e, exc_info=True)
        if progress_callback:
            progress_callback(f"Remotive error: {e}")

    return jobs


def _parse_job_type(raw: str) -> str | None:
    """Map Remotive job_type strings to normalized types."""
    if not raw:
        return None
    raw_lower = raw.lower().strip()
    if "full" in raw_lower:
        return "fulltime"
    if "part" in raw_lower:
        return "parttime"
    if "contract" in raw_lower or "freelance" in raw_lower:
        return "contract"
    if "intern" in raw_lower:
        return "internship"
    return raw_lower


def _parse_salary(salary_str: str) -> tuple[float | None, float | None, str | None]:
    """
    Attempt to parse a salary string like "$80,000 - $120,000" or "€60k-80k".

    Returns: (min, max, currency)
    """
    if not salary_str:
        return None, None, None

    import re

    # Detect currency
    currency = None
    if "$" in salary_str:
        currency = "USD"
    elif "€" in salary_str:
        currency = "EUR"
    elif "£" in salary_str:
        currency = "GBP"

    # Extract numbers
    numbers = re.findall(r"[\d,]+\.?\d*", salary_str.replace(",", ""))
    try:
        if len(numbers) >= 2:
            sal_min = float(numbers[0])
            sal_max = float(numbers[1])
            # Handle "k" suffix (e.g., "80k" → 80000)
            if "k" in salary_str.lower():
                if sal_min < 1000:
                    sal_min *= 1000
                if sal_max < 1000:
                    sal_max *= 1000
            return sal_min, sal_max, currency
        elif len(numbers) == 1:
            sal = float(numbers[0])
            if "k" in salary_str.lower() and sal < 1000:
                sal *= 1000
            return sal, sal, currency
    except (ValueError, IndexError):
        pass

    return None, None, None
