"""
scrapers/ats/lever.py — Lever Postings API scraper.

Uses the public Lever API:
    https://api.lever.co/v0/postings/{company_slug}

No authentication required. Returns JSON array of job postings.
"""

import logging
import re

from scrapers.ats.base import BaseATSScraper
from scrapers.ats.utils import strip_html as _strip_html
from processing.search_filter import matches_search_term, matches_location

logger = logging.getLogger(__name__)

API_BASE = "https://api.lever.co/v0/postings"


class LeverScraper(BaseATSScraper):
    """Scraper for Lever postings API."""

    def scrape_job(self, url: str) -> dict | None:
        """
        Scrape a single Lever job from URL.

        Extracts company_slug from the URL, finds the specific posting.

        Args:
            url: A Lever job URL like https://jobs.lever.co/{company}/{job_id}

        Returns:
            Unified schema dict or None on failure.
        """
        try:
            match = re.search(r"jobs\.lever\.co/([\w-]+)/([\w-]+)", url)
            if not match:
                match = re.search(r"jobs\.lever\.co/([\w-]+)", url)
                if match:
                    return None  # Can't identify specific job, scrape_company is better
                logger.warning("Could not parse Lever URL: %s", url)
                return None

            company_slug = match.group(1)
            job_id = match.group(2) if match.lastindex >= 2 else None

            if job_id:
                # Fetch specific job
                api_url = f"{API_BASE}/{company_slug}/{job_id}"
                resp = self._get(api_url)
                if resp:
                    data = resp.json()
                    return self._map_job(data, company_slug)

            return None

        except Exception as e:
            logger.error("Error scraping Lever job %s: %s", url, e)
            return None

    def scrape_company(
        self,
        company_slug: str,
        search_term: str | None = None,
        location: str | None = None,
    ) -> list[dict]:
        """
        Scrape ALL jobs from a Lever company board via API.

        Args:
            company_slug: The company identifier.
            search_term: Optional keyword filter.
            location: Optional location filter.

        Returns:
            List of unified schema dicts.
        """
        jobs: list[dict] = []

        try:
            api_url = f"{API_BASE}/{company_slug}"
            logger.info("Fetching Lever jobs for company: %s", company_slug)

            resp = self._get(api_url)
            if not resp:
                logger.warning("Failed to fetch Lever board for %s", company_slug)
                return jobs

            data = resp.json()
            if not isinstance(data, list):
                logger.warning("Lever response for %s is not a list.", company_slug)
                return jobs

            logger.info("Lever %s: %d total jobs found.", company_slug, len(data))

            for item in data:
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
                    logger.warning("Error mapping Lever job from %s: %s", company_slug, e)
                    continue

            logger.info("Lever %s: %d jobs after filtering.", company_slug, len(jobs))

        except Exception as e:
            logger.error("Error scraping Lever company %s: %s", company_slug, e, exc_info=True)

        return jobs

    def _map_job(self, data: dict, company_slug: str) -> dict | None:
        """Map a Lever API posting object to the unified schema."""
        if not data:
            return None

        job = self._empty_job()

        job["source"] = "ats_discovery"
        job["ats_platform"] = "lever"
        job["title"] = data.get("text")
        job["company"] = company_slug.replace("-", " ").title()

        # Location
        categories = data.get("categories", {})
        if isinstance(categories, dict):
            job["location"] = categories.get("location")
            # Department can give additional context
            department = categories.get("department")
            commitment = categories.get("commitment")
            if commitment:
                commitment_lower = commitment.lower()
                if "full" in commitment_lower:
                    job["job_type"] = "fulltime"
                elif "part" in commitment_lower:
                    job["job_type"] = "parttime"
                elif "intern" in commitment_lower:
                    job["job_type"] = "internship"
                elif "contract" in commitment_lower:
                    job["job_type"] = "contract"

        # Job URL — use hostedUrl from response
        job["job_url"] = data.get("hostedUrl") or data.get("applyUrl")
        if not job["job_url"]:
            job_id = data.get("id")
            if job_id:
                job["job_url"] = f"https://jobs.lever.co/{company_slug}/{job_id}"

        # Description — combine lists sections
        description_parts = []
        desc_plain = data.get("descriptionPlain")
        if desc_plain:
            description_parts.append(desc_plain)

        # Additional lists (requirements, responsibilities, etc.)
        lists = data.get("lists", [])
        for lst in lists:
            section_title = lst.get("text", "")
            section_content = lst.get("content", "")
            if section_title:
                description_parts.append(f"\n{section_title}")
            if section_content:
                clean = _strip_html(section_content)
                description_parts.append(clean)

        # Additional section
        additional = data.get("additional")
        if additional:
            description_parts.append(_strip_html(additional))

        job["description"] = "\n\n".join(description_parts) if description_parts else None

        # Date posted
        created_at = data.get("createdAt")
        if created_at:
            try:
                # Lever timestamps are in milliseconds
                import datetime
                dt = datetime.datetime.fromtimestamp(created_at / 1000)
                job["date_posted"] = dt.strftime("%Y-%m-%d")
            except Exception:
                pass

        # Check for remote
        loc_str = (job.get("location") or "").lower()
        title_str = (job.get("title") or "").lower()
        if "remote" in loc_str or "remote" in title_str:
            job["is_remote"] = True

        # Company URL
        job["company_url"] = f"https://jobs.lever.co/{company_slug}"

        return job


# Module-level instance
_scraper = LeverScraper()


def scrape_lever_job(url: str) -> dict | None:
    """Convenience function: scrape a single Lever job."""
    return _scraper.scrape_job(url)


def scrape_lever_company(
    company_slug: str,
    search_term: str | None = None,
    location: str | None = None,
) -> list[dict]:
    """Convenience function: scrape all jobs for a Lever company."""
    return _scraper.scrape_company(company_slug, search_term, location)
