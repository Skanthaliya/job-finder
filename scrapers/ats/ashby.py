"""
scrapers/ats/ashby.py — Ashby Job Board API scraper.

Uses the public Ashby API:
    https://api.ashbyhq.com/posting-api/job-board/{company_slug}

No authentication required. Returns JSON with job postings.
"""

import logging
import re
from html import unescape

from scrapers.ats.base import BaseATSScraper

logger = logging.getLogger(__name__)

API_BASE = "https://api.ashbyhq.com/posting-api/job-board"


class AshbyScraper(BaseATSScraper):
    """Scraper for Ashby job board API."""

    def scrape_job(self, url: str) -> dict | None:
        """
        Scrape a single Ashby job from URL.

        Args:
            url: An Ashby job URL like https://jobs.ashbyhq.com/{company}/{job_id}

        Returns:
            Unified schema dict or None on failure.
        """
        try:
            match = re.search(r"jobs\.ashbyhq\.com/([\w-]+)/([\w-]+)", url)
            if not match:
                match = re.search(r"jobs\.ashbyhq\.com/([\w-]+)", url)
                if match:
                    # Only have company slug, can't get specific job
                    return None
                logger.warning("Could not parse Ashby URL: %s", url)
                return None

            company_slug = match.group(1)
            job_id = match.group(2)

            # Ashby doesn't have a single-job API, so we fetch all and filter
            all_jobs = self.scrape_company(company_slug)
            for j in all_jobs:
                if job_id in (j.get("job_url") or ""):
                    return j

            return None

        except Exception as e:
            logger.error("Error scraping Ashby job %s: %s", url, e)
            return None

    def scrape_company(
        self,
        company_slug: str,
        search_term: str | None = None,
        location: str | None = None,
    ) -> list[dict]:
        """
        Scrape all jobs from an Ashby company board via API.

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
            logger.info("Fetching Ashby jobs for company: %s", company_slug)

            resp = self._get(api_url)
            if not resp:
                logger.warning("Failed to fetch Ashby board for %s", company_slug)
                return jobs

            data = resp.json()
            all_jobs = data.get("jobs", [])
            logger.info("Ashby %s: %d total jobs found.", company_slug, len(all_jobs))

            search_lower = search_term.lower() if search_term else ""
            location_lower = location.lower() if location else ""

            for item in all_jobs:
                try:
                    mapped = self._map_job(item, company_slug)
                    if not mapped:
                        continue

                    # Filter by search term
                    if search_lower:
                        title = (mapped.get("title") or "").lower()
                        desc = (mapped.get("description") or "").lower()
                        search_words = search_lower.split()
                        if not any(w in title or w in desc for w in search_words):
                            continue

                    # Filter by location
                    if location_lower:
                        job_loc = (mapped.get("location") or "").lower()
                        if location_lower not in job_loc:
                            continue

                    jobs.append(mapped)

                except Exception as e:
                    logger.warning("Error mapping Ashby job from %s: %s", company_slug, e)
                    continue

            logger.info("Ashby %s: %d jobs after filtering.", company_slug, len(jobs))

        except Exception as e:
            logger.error("Error scraping Ashby company %s: %s", company_slug, e, exc_info=True)

        return jobs

    def _map_job(self, data: dict, company_slug: str) -> dict | None:
        """Map an Ashby API job object to the unified schema."""
        if not data:
            return None

        job = self._empty_job()
        job["source"] = "google_dork"
        job["ats_platform"] = "ashby"
        job["title"] = data.get("title")
        job["company"] = company_slug.replace("-", " ").title()

        # Location
        location = data.get("location")
        if isinstance(location, str):
            job["location"] = location
        elif isinstance(location, dict):
            job["location"] = location.get("name")

        # Secondary locations
        secondary = data.get("secondaryLocations", [])
        if secondary and isinstance(secondary, list):
            locs = [job["location"]] if job["location"] else []
            for loc in secondary:
                if isinstance(loc, str):
                    locs.append(loc)
                elif isinstance(loc, dict):
                    locs.append(loc.get("name", ""))
            job["location"] = ", ".join(locs)

        # Job URL
        job_id = data.get("id")
        job_url = data.get("jobUrl") or data.get("hostedUrl")
        if job_url:
            job["job_url"] = job_url
        elif job_id:
            job["job_url"] = f"https://jobs.ashbyhq.com/{company_slug}/{job_id}"

        # Department
        department = data.get("department")
        if isinstance(department, str):
            pass  # Not in our schema but could be useful
        elif isinstance(department, dict):
            pass

        # Employment type
        employment_type = data.get("employmentType") or ""
        emp_lower = employment_type.lower()
        if "full" in emp_lower:
            job["job_type"] = "fulltime"
        elif "part" in emp_lower:
            job["job_type"] = "parttime"
        elif "contract" in emp_lower:
            job["job_type"] = "contract"
        elif "intern" in emp_lower:
            job["job_type"] = "internship"

        # Remote
        is_remote = data.get("isRemote")
        if is_remote is not None:
            job["is_remote"] = bool(is_remote)
        elif "remote" in (job.get("location") or "").lower():
            job["is_remote"] = True

        # Description
        desc = data.get("descriptionHtml") or data.get("description") or data.get("descriptionPlain")
        if desc:
            if "<" in desc:
                job["description"] = _strip_html(desc)
            else:
                job["description"] = desc

        # Date
        published = data.get("publishedDate") or data.get("updatedAt") or data.get("createdAt")
        if published:
            job["date_posted"] = str(published)[:10]

        # Compensation
        comp = data.get("compensation")
        if comp and isinstance(comp, dict):
            salary_range = comp.get("range")
            if salary_range and isinstance(salary_range, dict):
                job["salary_min"] = salary_range.get("min")
                job["salary_max"] = salary_range.get("max")
            job["salary_currency"] = comp.get("currency")
            interval = comp.get("interval") or comp.get("period")
            if interval:
                job["salary_interval"] = interval.lower()

        job["company_url"] = f"https://jobs.ashbyhq.com/{company_slug}"
        return job


def _strip_html(html_text: str) -> str:
    """Strip HTML tags from text."""
    text = re.sub(r"<br\s*/?>", "\n", html_text)
    text = re.sub(r"<p>", "\n", text)
    text = re.sub(r"</p>", "\n", text)
    text = re.sub(r"<li>", "\n• ", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# Module-level instance
_scraper = AshbyScraper()


def scrape_ashby_job(url: str) -> dict | None:
    """Convenience: scrape a single Ashby job."""
    return _scraper.scrape_job(url)


def scrape_ashby_company(
    company_slug: str,
    search_term: str | None = None,
    location: str | None = None,
) -> list[dict]:
    """Convenience: scrape all jobs for an Ashby company."""
    return _scraper.scrape_company(company_slug, search_term, location)
