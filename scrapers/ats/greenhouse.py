"""
scrapers/ats/greenhouse.py — Greenhouse Job Board API scraper.

Uses the public Greenhouse API:
    https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs

No authentication required. Returns JSON with all jobs for a company.
"""

import logging
import re

from scrapers.ats.base import BaseATSScraper
from scrapers.ats.utils import strip_html as _strip_html
from processing.search_filter import matches_search_term, matches_location

logger = logging.getLogger(__name__)

API_BASE = "https://boards-api.greenhouse.io/v1/boards"
BOARD_URL_BASE = "https://boards.greenhouse.io"


class GreenhouseScraper(BaseATSScraper):
    """Scraper for Greenhouse job board API."""

    def scrape_job(self, url: str) -> dict | None:
        """
        Scrape a single Greenhouse job from URL.

        Extracts company_slug and job_id from the URL, then fetches via API.

        Args:
            url: A Greenhouse job URL like
                 https://boards.greenhouse.io/{company}/jobs/{id}

        Returns:
            Unified schema dict or None on failure.
        """
        try:
            # Extract company_slug and job_id from URL
            match = re.search(r"boards\.greenhouse\.io/([\w-]+)/jobs/(\d+)", url)
            if not match:
                # Try alternate pattern
                match = re.search(r"boards\.greenhouse\.io/([\w-]+)", url)
                if match:
                    return None
                logger.warning("Could not parse Greenhouse URL: %s", url)
                return None

            company_slug = match.group(1)
            job_id = match.group(2)

            api_url = f"{API_BASE}/{company_slug}/jobs/{job_id}"
            resp = self._get(api_url)
            if not resp:
                return None

            data = resp.json()
            return self._map_job(data, company_slug)

        except Exception as e:
            logger.error("Error scraping Greenhouse job %s: %s", url, e)
            return None

    def scrape_company(
        self,
        company_slug: str,
        search_term: str | None = None,
        location: str | None = None,
    ) -> list[dict]:
        """
        Scrape ALL jobs from a Greenhouse company board via API.

        Optionally filters by search_term (in title/description) and location.

        Args:
            company_slug: The company identifier (e.g., "airbnb").
            search_term: Optional keyword filter.
            location: Optional location filter.

        Returns:
            List of unified schema dicts.
        """
        jobs: list[dict] = []

        try:
            api_url = f"{API_BASE}/{company_slug}/jobs"
            params = {"content": "true"}  # Include full descriptions

            logger.info("Fetching Greenhouse jobs for company: %s", company_slug)
            resp = self._get(api_url, params=params)
            if not resp:
                logger.warning("Failed to fetch Greenhouse board for %s", company_slug)
                return jobs

            data = resp.json()
            all_jobs = data.get("jobs", [])
            logger.info("Greenhouse %s: %d total jobs found.", company_slug, len(all_jobs))

            for item in all_jobs:
                try:
                    mapped = self._map_job(item, company_slug)
                    if not mapped:
                        continue

                    if search_term and not matches_search_term(mapped, search_term):
                        continue
                    if location and not matches_location(mapped, location):
                        continue

                    jobs.append(mapped)

                except Exception as e:
                    logger.warning("Error mapping Greenhouse job from %s: %s", company_slug, e)
                    continue

            logger.info("Greenhouse %s: %d jobs after filtering.", company_slug, len(jobs))

        except Exception as e:
            logger.error("Error scraping Greenhouse company %s: %s", company_slug, e, exc_info=True)

        return jobs

    def _map_job(self, data: dict, company_slug: str) -> dict | None:
        """Map a Greenhouse API job object to the unified schema."""
        if not data:
            return None

        job = self._empty_job()

        job["source"] = "ats_discovery"
        job["ats_platform"] = "greenhouse"
        job["title"] = data.get("title")

        # Company name — from departments or from slug
        company_name = company_slug.replace("-", " ").title()
        # Try to get from metadata if available
        if data.get("company"):
            company_name = data["company"].get("name", company_name)
        job["company"] = company_name

        # Location
        loc = data.get("location", {})
        if isinstance(loc, dict):
            job["location"] = loc.get("name")
        elif isinstance(loc, str):
            job["location"] = loc

        # Job URL
        job_id = data.get("id")
        job["job_url"] = f"{BOARD_URL_BASE}/{company_slug}/jobs/{job_id}" if job_id else None

        # Description (HTML content)
        content = data.get("content")
        if content:
            # Strip HTML tags for description text
            job["description"] = _strip_html(content)

        # Date posted
        updated_at = data.get("updated_at") or data.get("first_published")
        if updated_at:
            job["date_posted"] = str(updated_at)[:10]

        # Check for remote in location or title
        loc_str = (job.get("location") or "").lower()
        title_str = (job.get("title") or "").lower()
        if "remote" in loc_str or "remote" in title_str:
            job["is_remote"] = True

        # Company URL
        job["company_url"] = f"{BOARD_URL_BASE}/{company_slug}"

        return job


# Module-level instance for convenience
_scraper = GreenhouseScraper()


def scrape_greenhouse_job(url: str) -> dict | None:
    """Convenience function: scrape a single Greenhouse job."""
    return _scraper.scrape_job(url)


def scrape_greenhouse_company(
    company_slug: str,
    search_term: str | None = None,
    location: str | None = None,
) -> list[dict]:
    """Convenience function: scrape all jobs for a Greenhouse company."""
    return _scraper.scrape_company(company_slug, search_term, location)
