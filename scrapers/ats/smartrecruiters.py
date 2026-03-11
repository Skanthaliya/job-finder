"""
scrapers/ats/smartrecruiters.py — SmartRecruiters API scraper.

Uses the public SmartRecruiters API:
    https://api.smartrecruiters.com/v1/companies/{company_slug}/postings

Supports query params: ?q={search_term}&location={location}
No authentication required.
"""

import logging
import re
from datetime import datetime, timedelta
from html import unescape

from scrapers.ats.base import BaseATSScraper

logger = logging.getLogger(__name__)

API_BASE = "https://api.smartrecruiters.com/v1/companies"


class SmartRecruitersScraper(BaseATSScraper):
    """Scraper for SmartRecruiters public API."""

    def scrape_job(self, url: str) -> dict | None:
        """
        Scrape a single SmartRecruiters job from URL.

        Args:
            url: A SmartRecruiters job URL like
                 https://jobs.smartrecruiters.com/{company}/{job_id}

        Returns:
            Unified schema dict or None on failure.
        """
        try:
            match = re.search(r"jobs\.smartrecruiters\.com/([\w-]+)/([\w-]+)", url)
            if not match:
                match = re.search(r"jobs\.smartrecruiters\.com/([\w-]+)", url)
                if match:
                    return None
                logger.warning("Could not parse SmartRecruiters URL: %s", url)
                return None

            company_slug = match.group(1)
            job_id = match.group(2)

            # Try API for specific posting
            api_url = f"{API_BASE}/{company_slug}/postings/{job_id}"
            resp = self._get(api_url, headers={"Accept": "application/json"})
            if resp:
                data = resp.json()
                return self._map_job(data, company_slug)

            return None

        except Exception as e:
            logger.error("Error scraping SmartRecruiters job %s: %s", url, e)
            return None

    def scrape_company(
        self,
        company_slug: str,
        search_term: str | None = None,
        location: str | None = None,
    ) -> list[dict]:
        """
        Scrape all jobs from a SmartRecruiters company via API.

        Args:
            company_slug: The company identifier.
            search_term: Optional search text.
            location: Optional location filter.

        Returns:
            List of unified schema dicts.
        """
        jobs: list[dict] = []

        try:
            api_url = f"{API_BASE}/{company_slug}/postings"
            params = {}
            if search_term:
                params["q"] = search_term
            if location:
                params["location"] = location

            logger.info("Fetching SmartRecruiters jobs for company: %s", company_slug)

            offset = 0
            limit = 100
            total_fetched = 0

            while True:
                params["offset"] = offset
                params["limit"] = limit

                resp = self._get(api_url, params=params, headers={"Accept": "application/json"})
                if not resp:
                    break

                data = resp.json()
                content = data.get("content", [])
                total_found = data.get("totalFound", 0)

                if not content:
                    break

                for item in content:
                    try:
                        # Skip old jobs (> 90 days)
                        cutoff_date = datetime.now() - timedelta(days=90)
                        created = item.get("releasedDate") or item.get("createdOn") or ""
                        if created:
                            try:
                                if isinstance(created, str):
                                    post_date = datetime.fromisoformat(created.replace("Z", "+00:00"))
                                    if post_date.replace(tzinfo=None) < cutoff_date:
                                        continue
                            except Exception:
                                pass

                        mapped = self._map_job(item, company_slug)
                        if mapped:
                            jobs.append(mapped)
                    except Exception as e:
                        logger.warning("Error mapping SmartRecruiters job: %s", e)
                        continue

                total_fetched += len(content)
                offset += limit

                if total_fetched >= total_found:
                    break

            logger.info("SmartRecruiters %s: %d jobs found.", company_slug, len(jobs))

        except Exception as e:
            logger.error("Error scraping SmartRecruiters company %s: %s", company_slug, e, exc_info=True)

        return jobs

    def _map_job(self, data: dict, company_slug: str) -> dict | None:
        """Map a SmartRecruiters API posting object to the unified schema."""
        if not data:
            return None

        job = self._empty_job()
        job["source"] = "google_dork"
        job["ats_platform"] = "smartrecruiters"
        job["title"] = data.get("name") or data.get("title")

        # Company
        company_info = data.get("company", {})
        if isinstance(company_info, dict):
            job["company"] = company_info.get("name") or company_slug.replace("-", " ").title()
        else:
            job["company"] = company_slug.replace("-", " ").title()

        # Location
        loc = data.get("location", {})
        if isinstance(loc, dict):
            city = loc.get("city", "")
            region = loc.get("region", "")
            country = loc.get("country", "")
            loc_parts = [p for p in [city, region, country] if p]
            job["location"] = ", ".join(loc_parts) if loc_parts else None
            job["country"] = country
        elif isinstance(loc, str):
            job["location"] = loc

        # Check for remote
        remote_status = loc.get("remote", False) if isinstance(loc, dict) else False
        if remote_status:
            job["is_remote"] = True
        elif "remote" in (job.get("location") or "").lower():
            job["is_remote"] = True

        # Job URL
        job_ref = data.get("ref") or ""
        posting_id = data.get("id") or data.get("uuid") or ""
        custom_url = data.get("customCareerSiteUrl")
        if custom_url:
            job["job_url"] = custom_url
        elif job_ref and "api.smartrecruiters.com" not in job_ref:
            job["job_url"] = job_ref
        elif posting_id:
            job["job_url"] = f"https://jobs.smartrecruiters.com/{company_slug}/{posting_id}"
        else:
            job["job_url"] = f"https://jobs.smartrecruiters.com/{company_slug}"

        # Description
        desc = data.get("jobDescription") or ""
        qualifications = data.get("qualifications") or ""
        additional = data.get("additionalInformation") or ""
        desc_parts = [d for d in [desc, qualifications, additional] if d]
        if desc_parts:
            combined = "\n\n".join(desc_parts)
            job["description"] = _strip_html(combined) if "<" in combined else combined

        # Date posted
        released_date = data.get("releasedDate") or data.get("createdOn")
        if released_date:
            job["date_posted"] = str(released_date)[:10]

        # Job type / experience
        experience = data.get("experienceLevel", {})
        if isinstance(experience, dict):
            exp_id = (experience.get("id") or "").lower()
            if "intern" in exp_id:
                job["job_type"] = "internship"

        type_of_employment = data.get("typeOfEmployment", {})
        if isinstance(type_of_employment, dict):
            emp_id = (type_of_employment.get("id") or "").lower()
            if "full" in emp_id:
                job["job_type"] = "fulltime"
            elif "part" in emp_id:
                job["job_type"] = "parttime"
            elif "contract" in emp_id:
                job["job_type"] = "contract"

        # Salary/compensation
        compensation = data.get("compensation", {})
        if isinstance(compensation, dict):
            salary_range = compensation.get("range") or {}
            if isinstance(salary_range, dict):
                job["salary_min"] = salary_range.get("min")
                job["salary_max"] = salary_range.get("max")
            job["salary_currency"] = compensation.get("currency")

        job["company_url"] = f"https://jobs.smartrecruiters.com/{company_slug}"
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
_scraper = SmartRecruitersScraper()


def scrape_sr_job(url: str) -> dict | None:
    """Convenience: scrape a single SmartRecruiters job."""
    return _scraper.scrape_job(url)


def scrape_sr_company(
    company_slug: str,
    search_term: str | None = None,
    location: str | None = None,
) -> list[dict]:
    """Convenience: scrape all jobs for a SmartRecruiters company."""
    return _scraper.scrape_company(company_slug, search_term, location)
