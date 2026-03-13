"""
scrapers/ats/personio.py — Personio career page scraper.

Personio career pages at {company}.jobs.personio.de
Attempts XML feed first, falls back to HTML scraping.
"""

import logging
import re
import xml.etree.ElementTree as ET
from html import unescape
from urllib.parse import urlparse

from scrapers.ats.base import BaseATSScraper

logger = logging.getLogger(__name__)


class PersonioScraper(BaseATSScraper):
    """Scraper for Personio career pages."""

    def scrape_job(self, url: str) -> dict | None:
        """
        Scrape a single Personio job from URL.

        Args:
            url: A Personio job URL.

        Returns:
            Unified schema dict or None on failure.
        """
        try:
            # Try to get the page and extract job info
            resp = self._get(url)
            if not resp:
                return self._fallback_from_url(url)

            return self._parse_html_job(resp.text, url)

        except Exception as e:
            logger.error("Error scraping Personio job %s: %s", url, e)
            return self._fallback_from_url(url)

    def scrape_company(
        self,
        company_slug: str,
        search_term: str | None = None,
        location: str | None = None,
    ) -> list[dict]:
        """
        Scrape all jobs from a Personio company career page.

        Tries the XML feed first, falls back to HTML scraping.

        Args:
            company_slug: The company identifier (e.g., "mycompany").
            search_term: Optional keyword filter.
            location: Optional location filter.

        Returns:
            List of unified schema dicts.
        """
        jobs: list[dict] = []

        try:
            base_url = f"https://{company_slug}.jobs.personio.de"

            # --- Try XML feed first ---
            xml_url = f"{base_url}/xml"
            logger.info("Trying Personio XML feed: %s", xml_url)
            xml_resp = self._get(xml_url)

            if xml_resp and xml_resp.status_code == 200:
                try:
                    jobs = self._parse_xml_feed(xml_resp.text, company_slug, search_term, location)
                    if jobs:
                        logger.info("Personio %s: %d jobs from XML feed.", company_slug, len(jobs))
                        return jobs
                except Exception as e:
                    logger.debug("XML parsing failed for %s: %s", company_slug, e)

            # --- Fallback: HTML scraping ---
            logger.info("Falling back to HTML scraping for Personio: %s", base_url)
            html_resp = self._get(base_url)
            if html_resp:
                jobs = self._parse_html_listing(html_resp.text, base_url, company_slug, search_term, location)

            logger.info("Personio %s: %d jobs found.", company_slug, len(jobs))

        except Exception as e:
            logger.error("Error scraping Personio company %s: %s", company_slug, e, exc_info=True)

        return jobs

    def _parse_xml_feed(
        self, xml_text: str, company_slug: str,
        search_term: str | None, location: str | None,
    ) -> list[dict]:
        """Parse Personio XML job feed."""
        jobs = []
        root = ET.fromstring(xml_text)

        search_lower = search_term.lower() if search_term else ""
        location_lower = location.lower() if location else ""

        for position in root.iter("position"):
            try:
                job = self._empty_job()
                job["source"] = "ats_discovery"
                job["ats_platform"] = "personio"
                job["company"] = company_slug.replace("-", " ").title()

                job["title"] = _get_xml_text(position, "name")
                job["location"] = _get_xml_text(position, "office")
                job["department"] = _get_xml_text(position, "department")

                # Job URL
                job_id = _get_xml_text(position, "id")
                if job_id:
                    job["job_url"] = f"https://{company_slug}.jobs.personio.de/job/{job_id}"

                # Description
                desc_parts = []
                for field_name in ["jobDescription", "description", "recruitingCategory"]:
                    text = _get_xml_text(position, field_name)
                    if text:
                        desc_parts.append(text)
                job["description"] = "\n\n".join(desc_parts) if desc_parts else None

                # Date
                created = _get_xml_text(position, "createdAt")
                if created:
                    job["date_posted"] = created[:10]

                # Employment type
                schedule = _get_xml_text(position, "schedule") or ""
                if "full" in schedule.lower():
                    job["job_type"] = "fulltime"
                elif "part" in schedule.lower():
                    job["job_type"] = "parttime"

                # Filter
                if search_lower:
                    searchable = f"{job.get('title', '')} {job.get('description', '')}".lower()
                    words = search_lower.split()
                    if not any(w in searchable for w in words):
                        continue

                if location_lower and location_lower not in (job.get("location") or "").lower():
                    continue

                job["company_url"] = f"https://{company_slug}.jobs.personio.de"

                if job.get("job_url"):
                    jobs.append(job)

            except Exception as e:
                logger.warning("Error parsing Personio XML position: %s", e)
                continue

        return jobs

    def _parse_html_listing(
        self, html_text: str, base_url: str, company_slug: str,
        search_term: str | None, location: str | None,
    ) -> list[dict]:
        """Parse Personio HTML career page listing."""
        jobs = []

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "lxml")

            # Personio uses various CSS patterns for job listings
            job_elements = soup.select("a.job-listing, a[data-position-id], .position-card a, .job-item a")

            if not job_elements:
                # Try broader search
                job_elements = soup.find_all("a", href=re.compile(r"/job/\d+"))

            search_lower = search_term.lower() if search_term else ""
            location_lower = location.lower() if location else ""

            for elem in job_elements:
                try:
                    job = self._empty_job()
                    job["source"] = "ats_discovery"
                    job["ats_platform"] = "personio"
                    job["company"] = company_slug.replace("-", " ").title()

                    # Title from link text
                    title_elem = elem.select_one(".job-title, .position-title, h3, h4") or elem
                    job["title"] = title_elem.get_text(strip=True)

                    # URL
                    href = elem.get("href", "")
                    if href and not href.startswith("http"):
                        href = base_url.rstrip("/") + "/" + href.lstrip("/")
                    job["job_url"] = href

                    # Location
                    loc_elem = elem.select_one(".job-location, .position-location, .location")
                    if loc_elem:
                        job["location"] = loc_elem.get_text(strip=True)

                    # Filter
                    if search_lower and search_lower not in (job.get("title") or "").lower():
                        continue
                    if location_lower and location_lower not in (job.get("location") or "").lower():
                        continue

                    job["company_url"] = base_url

                    if job.get("job_url") and job.get("title"):
                        jobs.append(job)

                except Exception as e:
                    logger.warning("Error parsing Personio HTML job element: %s", e)
                    continue

        except ImportError:
            logger.error("BeautifulSoup not installed for Personio HTML parsing.")
        except Exception as e:
            logger.error("Error parsing Personio HTML: %s", e)

        return jobs

    def _parse_html_job(self, html_text: str, url: str) -> dict | None:
        """Parse a single Personio job page HTML."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "lxml")

            job = self._empty_job()
            job["source"] = "ats_discovery"
            job["ats_platform"] = "personio"
            job["job_url"] = url

            # Extract company from domain
            parsed = urlparse(url)
            hostname = parsed.hostname or ""
            match = re.match(r"([\w-]+)\.jobs\.personio\.de", hostname)
            if match:
                job["company"] = match.group(1).replace("-", " ").title()

            # Title
            title_elem = soup.select_one("h1.job-title, h1, .position-title")
            if title_elem:
                job["title"] = title_elem.get_text(strip=True)
            else:
                title_tag = soup.find("title")
                if title_tag:
                    job["title"] = title_tag.get_text(strip=True)

            # Description
            desc_elem = soup.select_one(".job-description, .position-description, .description, article")
            if desc_elem:
                job["description"] = desc_elem.get_text(separator="\n", strip=True)

            # Location
            loc_elem = soup.select_one(".job-location, .position-location, .location")
            if loc_elem:
                job["location"] = loc_elem.get_text(strip=True)

            return job

        except Exception as e:
            logger.error("Error parsing Personio HTML job: %s", e)
            return self._fallback_from_url(url)

    def _fallback_from_url(self, url: str) -> dict | None:
        """Create a minimal job entry from the URL."""
        job = self._empty_job()
        job["source"] = "ats_discovery"
        job["ats_platform"] = "personio"
        job["job_url"] = url

        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        match = re.match(r"([\w-]+)\.jobs\.personio\.de", hostname)
        if match:
            job["company"] = match.group(1).replace("-", " ").title()

        return job


def _get_xml_text(element: ET.Element, tag: str) -> str | None:
    """Safely get text from an XML child element."""
    child = element.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    return None


# Module-level instance
_scraper = PersonioScraper()


def scrape_personio_job(url: str) -> dict | None:
    """Convenience: scrape a single Personio job."""
    return _scraper.scrape_job(url)


def scrape_personio_company(
    company_slug: str,
    search_term: str | None = None,
    location: str | None = None,
) -> list[dict]:
    """Convenience: scrape all jobs for a Personio company."""
    return _scraper.scrape_company(company_slug, search_term, location)
