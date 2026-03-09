"""
scrapers/jobspy_scraper.py — Wrapper around the python-jobspy library.

Calls jobspy.scrape_jobs() and maps the returned DataFrame to the unified job schema.
"""

import logging
from typing import Callable

import pandas as pd

from config import (
    DEFAULT_SEARCH_TERM,
    DEFAULT_LOCATION,
    DEFAULT_COUNTRY,
    DEFAULT_HOURS_OLD,
    DEFAULT_RESULTS_PER_SITE,
    JOBSPY_SITES,
)

logger = logging.getLogger(__name__)


def scrape_jobspy(
    search_term: str = DEFAULT_SEARCH_TERM,
    location: str = DEFAULT_LOCATION,
    sites: list[str] | None = None,
    hours_old: int = DEFAULT_HOURS_OLD,
    results_wanted: int = DEFAULT_RESULTS_PER_SITE,
    country_indeed: str = DEFAULT_COUNTRY,
    job_type: str | None = None,
    is_remote: bool = False,
    progress_callback: Callable[[str], None] | None = None,
) -> list[dict]:
    """
    Scrape jobs from major job boards using the python-jobspy library.

    Args:
        search_term: Job title or keywords to search for.
        location: City or region to search in.
        sites: List of job board site names (e.g. ["indeed", "linkedin"]).
        hours_old: Only return jobs posted within this many hours.
        results_wanted: Maximum results to fetch per site.
        country_indeed: Country for Indeed search (e.g. "Germany", "USA").
        job_type: Filter by job type ("fulltime", "parttime", "contract", "internship").
        is_remote: If True, only return remote jobs.
        progress_callback: Optional function for progress updates.

    Returns:
        List of dicts matching the unified job schema.
    """
    if sites is None:
        sites = JOBSPY_SITES[:3]  # default: indeed, linkedin, google

    if progress_callback:
        progress_callback(f"Starting JobSpy scraper for '{search_term}' in '{location}' on {', '.join(sites)}...")

    jobs: list[dict] = []

    try:
        from jobspy import scrape_jobs

        scrape_params = {
            "site_name": sites,
            "search_term": search_term,
            "location": location,
            "results_wanted": results_wanted,
            "hours_old": hours_old,
            "country_indeed": country_indeed,
        }

        if job_type and job_type.lower() != "any":
            scrape_params["job_type"] = job_type

        if is_remote:
            scrape_params["is_remote"] = True

        logger.info("Calling jobspy.scrape_jobs with params: %s", scrape_params)
        df: pd.DataFrame = scrape_jobs(**scrape_params)

        if df is None or df.empty:
            logger.info("JobSpy returned no results.")
            if progress_callback:
                progress_callback("JobSpy: No results found.")
            return jobs

        logger.info("JobSpy returned %d raw results.", len(df))
        if progress_callback:
            progress_callback(f"JobSpy: Found {len(df)} jobs. Mapping to unified schema...")

        # Map DataFrame columns to our unified schema
        for _, row in df.iterrows():
            try:
                job = _map_jobspy_row(row)
                if job and job.get("job_url"):
                    jobs.append(job)
            except Exception as e:
                logger.warning("Error mapping JobSpy row: %s", e)
                continue

        logger.info("JobSpy: Successfully mapped %d jobs.", len(jobs))
        if progress_callback:
            progress_callback(f"JobSpy: {len(jobs)} jobs processed successfully.")

    except ImportError:
        logger.error("python-jobspy is not installed. Run: pip install python-jobspy")
        if progress_callback:
            progress_callback("Error: python-jobspy not installed.")
    except Exception as e:
        logger.error("JobSpy scraper failed: %s", e, exc_info=True)
        if progress_callback:
            progress_callback(f"JobSpy error: {e}")

    return jobs


def _map_jobspy_row(row: pd.Series) -> dict:
    """
    Map a single row from the JobSpy DataFrame to the unified job schema.

    Args:
        row: A pandas Series representing one job result from JobSpy.

    Returns:
        A dict matching the unified schema.
    """

    def safe_get(field: str, default=None):
        """Safely retrieve a field from the row."""
        try:
            val = row.get(field, default)
            if pd.isna(val):
                return default
            return val
        except Exception:
            return default

    # Determine source site name
    site_name = safe_get("site", "unknown")
    if isinstance(site_name, str):
        site_name = site_name.lower().strip()

    # Extract job URL
    job_url = safe_get("job_url") or safe_get("job_url_direct") or safe_get("link")
    if job_url:
        job_url = str(job_url).strip()

    # Parse date_posted
    date_posted = safe_get("date_posted")
    if date_posted is not None:
        try:
            if isinstance(date_posted, str):
                date_posted = str(date_posted)[:10]  # YYYY-MM-DD
            else:
                date_posted = pd.Timestamp(date_posted).strftime("%Y-%m-%d")
        except Exception:
            date_posted = str(date_posted)[:10] if date_posted else None

    # Parse salary fields
    salary_min = safe_get("min_amount")
    salary_max = safe_get("max_amount")
    salary_currency = safe_get("currency")
    salary_interval = safe_get("interval")

    if salary_min is not None:
        try:
            salary_min = float(salary_min)
        except (ValueError, TypeError):
            salary_min = None
    if salary_max is not None:
        try:
            salary_max = float(salary_max)
        except (ValueError, TypeError):
            salary_max = None

    # Parse is_remote
    is_remote = safe_get("is_remote")
    if is_remote is not None:
        is_remote = bool(is_remote)

    # Parse job_type
    job_type = safe_get("job_type")
    if job_type:
        job_type = str(job_type).lower().strip()

    return {
        "source": site_name,
        "ats_platform": None,
        "title": safe_get("title"),
        "company": safe_get("company"),
        "location": safe_get("location"),
        "country": safe_get("country"),
        "date_posted": date_posted,
        "job_type": job_type,
        "is_remote": is_remote,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": str(salary_currency) if salary_currency else None,
        "salary_interval": str(salary_interval) if salary_interval else None,
        "job_url": job_url,
        "company_url": safe_get("company_url"),
        "description": safe_get("description"),
        "language": None,  # Detected later
        # Phase 2 AI fields
        "ai_score": None,
        "ai_reasoning": None,
        "ai_cover_letter": None,
        "ai_resume_bullets": None,
    }
