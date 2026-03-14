"""
scrapers/ats/workday.py — Workday internal API scraper.

Workday career pages use an internal API:
    POST https://{company}.wd{N}.myworkdayjobs.com/wday/cxs/{company}/{path}/jobs
    GET  https://{company}.wd{N}.myworkdayjobs.com/wday/cxs/{company}/{path}{externalPath}

This is the trickiest scraper — Workday URLs have varied structures.
"""

import logging
import re
import time
from urllib.parse import urlparse

from scrapers.ats.base import BaseATSScraper
from scrapers.ats.utils import strip_html as _strip_html

logger = logging.getLogger(__name__)


class WorkdayScraper(BaseATSScraper):
    """Scraper for Workday career pages via internal API."""

    def __init__(self) -> None:
        super().__init__()
        # Workday requires specific headers
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    def scrape_job(self, url: str) -> dict | None:
        """
        Scrape a single Workday job from URL.

        Parses the URL to extract company, wd number, and path,
        then hits the detail API for full job info.

        Args:
            url: A Workday job URL.

        Returns:
            Unified schema dict or None on failure.
        """
        try:
            parsed = self._parse_workday_url(url)
            if not parsed:
                logger.warning("Could not parse Workday URL: %s", url)
                # Return minimal info from URL
                return self._fallback_from_url(url)

            company, wd_num, path, external_path = parsed
            base_url = f"https://{company}.wd{wd_num}.myworkdayjobs.com"

            if external_path:
                # Fetch job detail
                detail_url = f"{base_url}/wday/cxs/{company}/{path}{external_path}"
                resp = self._get(detail_url)
                if resp:
                    try:
                        data = resp.json()
                        job_data = data.get("jobPostingInfo", data)
                        return self._map_detail_job(job_data, company, base_url, path, url)
                    except Exception as e:
                        logger.warning("Error parsing Workday detail for %s: %s", url, e)

            # Fallback: return minimal data from URL
            return self._fallback_from_url(url)

        except Exception as e:
            logger.error("Error scraping Workday job %s: %s", url, e)
            return self._fallback_from_url(url)

    def scrape_company(
        self,
        company_slug: str,
        search_term: str | None = None,
        location: str | None = None,
    ) -> list[dict]:
        """
        Scrape jobs from a Workday company career page via search API.

        The company_slug here should be a base URL like:
            {company}.wd{N}.myworkdayjobs.com/{locale}/{path}

        Args:
            company_slug: Base URL or URL-like identifier for the Workday site.
            search_term: Optional search text.
            location: Optional location filter (not supported by all Workday instances).

        Returns:
            List of unified schema dicts.
        """
        jobs: list[dict] = []

        try:
            # Parse the slug/URL
            parsed = self._parse_workday_url(company_slug)
            if not parsed:
                logger.warning("Could not parse Workday company slug: %s", company_slug)
                return jobs

            company, wd_num, path, _ = parsed
            base_url = f"https://{company}.wd{wd_num}.myworkdayjobs.com"
            search_url = f"{base_url}/wday/cxs/{company}/{path}/jobs"

            logger.info("Searching Workday %s for '%s'", company, search_term or "")

            offset = 0
            limit = 20
            total_fetched = 0
            max_results = 200  # Safety limit

            while total_fetched < max_results:
                payload = {
                    "appliedFacets": {},
                    "limit": limit,
                    "offset": offset,
                    "searchText": search_term or "",
                }

                resp = self._post(search_url, json_data=payload)
                if not resp:
                    break

                try:
                    data = resp.json()
                except Exception:
                    logger.warning("Invalid JSON from Workday search for %s", company)
                    break

                postings = data.get("jobPostings", [])
                total = data.get("total", 0)

                if not postings:
                    break

                for posting in postings:
                    try:
                        mapped = self._map_search_job(posting, company, base_url, path)
                        if mapped:
                            # Filter by location if specified
                            if location:
                                job_loc = (mapped.get("location") or "").lower()
                                if location.lower() not in job_loc:
                                    continue
                            jobs.append(mapped)
                    except Exception as e:
                        logger.warning("Error mapping Workday posting: %s", e)
                        continue

                total_fetched += len(postings)
                offset += limit

                if offset >= total:
                    break

                time.sleep(0.5)  # Brief delay between pages

            logger.info("Workday %s: %d jobs found.", company, len(jobs))

        except Exception as e:
            logger.error("Error scraping Workday company %s: %s", company_slug, e, exc_info=True)

        return jobs

    def _parse_workday_url(self, url: str) -> tuple[str, str, str, str | None] | None:
        """
        Parse a Workday URL to extract components.

        Returns: (company, wd_number, path, external_path) or None.
        """
        # Normalize URL
        if not url.startswith("http"):
            url = "https://" + url

        try:
            parsed = urlparse(url)
            hostname = parsed.hostname or ""

            # Extract company and wd number from hostname
            # Pattern: {company}.wd{N}.myworkdayjobs.com
            host_match = re.match(r"([\w-]+)\.wd(\d+)\.myworkdayjobs\.com", hostname)
            if not host_match:
                return None

            company = host_match.group(1)
            wd_num = host_match.group(2)

            # Parse the path
            path_parts = [p for p in parsed.path.strip("/").split("/") if p]

            if not path_parts:
                return None

            # The path structure is typically: /{locale}/{job-board-id}/job/{slug}/{id}
            # or: /{job-board-id}/job/{slug}/{id}
            # We need the "path" which is the job board identifier

            # Find the path segment (usually first or second after locale)
            external_path = None
            path = path_parts[0]

            # Check if first segment looks like a locale (en-US, de-DE, etc.)
            if re.match(r"^[a-z]{2}(-[A-Z]{2})?$", path_parts[0]) and len(path_parts) > 1:
                path = path_parts[1]

            # If there's a /job/ segment, everything from /job/ onwards is the external path
            full_path = parsed.path
            job_match = re.search(r"(/job/.+)$", full_path)
            if job_match:
                external_path = job_match.group(1)

            return company, wd_num, path, external_path

        except Exception as e:
            logger.debug("Error parsing Workday URL %s: %s", url, e)
            return None

    def _map_search_job(self, posting: dict, company: str, base_url: str, path: str) -> dict | None:
        """Map a Workday search result to the unified schema."""
        if not posting:
            return None

        job = self._empty_job()
        job["source"] = "ats_discovery"
        job["ats_platform"] = "workday"
        job["title"] = posting.get("title")
        job["company"] = company.replace("-", " ").title()

        # Location
        locales = posting.get("locationsText") or posting.get("bulletFields", [])
        if isinstance(locales, str):
            job["location"] = locales
        elif isinstance(locales, list) and locales:
            job["location"] = locales[0] if isinstance(locales[0], str) else str(locales[0])

        # Date posted
        posted_on = posting.get("postedOn")
        if posted_on:
            job["date_posted"] = str(posted_on)[:10]

        # External path for building URL
        external_path = posting.get("externalPath", "")
        if external_path:
            job["job_url"] = f"{base_url}/{path}{external_path}"
        else:
            job["job_url"] = base_url

        # Bullet fields can contain additional info
        bullet_fields = posting.get("bulletFields", [])
        if isinstance(bullet_fields, list):
            for bullet in bullet_fields:
                bullet_str = str(bullet).lower() if bullet else ""
                if "remote" in bullet_str:
                    job["is_remote"] = True
                if "full" in bullet_str and "time" in bullet_str:
                    job["job_type"] = "fulltime"
                elif "part" in bullet_str and "time" in bullet_str:
                    job["job_type"] = "parttime"

        job["company_url"] = f"{base_url}/{path}"
        return job

    def _map_detail_job(
        self, data: dict, company: str, base_url: str, path: str, original_url: str,
    ) -> dict | None:
        """Map a Workday job detail response to the unified schema."""
        if not data:
            return None

        job = self._empty_job()
        job["source"] = "ats_discovery"
        job["ats_platform"] = "workday"
        job["title"] = data.get("title") or data.get("jobPostingTitle")
        job["company"] = data.get("company") or company.replace("-", " ").title()
        job["location"] = data.get("location") or data.get("locationsText")
        job["job_url"] = original_url

        # Description
        desc = data.get("jobDescription") or data.get("description")
        if desc:
            job["description"] = _strip_html(desc) if "<" in desc else desc

        # Date
        posted = data.get("postedDate") or data.get("postedOn") or data.get("startDate")
        if posted:
            job["date_posted"] = str(posted)[:10]

        # Remote check
        loc_str = (job.get("location") or "").lower()
        if "remote" in loc_str or "remote" in (job.get("title") or "").lower():
            job["is_remote"] = True

        # Time type
        time_type = data.get("timeType") or data.get("jobSchedule") or ""
        time_type_lower = time_type.lower()
        if "full" in time_type_lower:
            job["job_type"] = "fulltime"
        elif "part" in time_type_lower:
            job["job_type"] = "parttime"

        job["company_url"] = f"{base_url}/{path}"
        return job

    def _fallback_from_url(self, url: str) -> dict | None:
        """Create a minimal job entry from the URL when API scraping fails."""
        job = self._empty_job()
        job["source"] = "ats_discovery"
        job["ats_platform"] = "workday"
        job["job_url"] = url

        # Try to extract company from hostname
        try:
            parsed = urlparse(url if url.startswith("http") else f"https://{url}")
            hostname = parsed.hostname or ""
            match = re.match(r"([\w-]+)\.wd\d+", hostname)
            if match:
                job["company"] = match.group(1).replace("-", " ").title()
        except Exception:
            pass

        # Try to extract title from URL path
        try:
            path = urlparse(url).path
            parts = path.strip("/").split("/")
            for part in reversed(parts):
                if part and part not in ("job", "en-US", "de-DE") and not part.isdigit():
                    job["title"] = part.replace("-", " ").replace("_", " ").title()
                    break
        except Exception:
            pass

        return job


# Module-level instance
_scraper = WorkdayScraper()


def scrape_workday_job(url: str) -> dict | None:
    """Convenience: scrape a single Workday job."""
    return _scraper.scrape_job(url)


def scrape_workday_company(
    company_base_url: str,
    search_term: str | None = None,
    location: str | None = None,
) -> list[dict]:
    """Convenience: scrape all jobs for a Workday company."""
    return _scraper.scrape_company(company_base_url, search_term, location)
