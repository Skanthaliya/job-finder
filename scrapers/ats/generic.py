"""
scrapers/ats/generic.py — Generic HTML scraper for unknown career pages.

Fallback scraper for URLs that don't match any known ATS pattern.
Uses requests + BeautifulSoup to extract whatever job information is available.
"""

import logging
import re
from html import unescape
from urllib.parse import urlparse

import requests

from scrapers.ats.base import BaseATSScraper

logger = logging.getLogger(__name__)


class GenericScraper(BaseATSScraper):
    """
    Generic fallback scraper for career pages that don't match known ATS platforms.

    Extracts basic information: title, company (from domain), description text.
    Returns minimal data — "something rather than nothing."
    """

    def scrape_job(self, url: str) -> dict | None:
        """
        Scrape a single job from a generic career page URL.

        Uses BeautifulSoup to extract whatever information is available
        from the page HTML.

        Args:
            url: Any career page URL.

        Returns:
            Unified schema dict with whatever data we could extract, or None.
        """
        try:
            resp = self._get(url)
            if not resp:
                return self._fallback_from_url(url)

            return self._parse_page(resp.text, url)

        except Exception as e:
            logger.error("Error scraping generic page %s: %s", url, e)
            return self._fallback_from_url(url)

    def scrape_company(
        self,
        company_slug: str,
        search_term: str | None = None,
        location: str | None = None,
    ) -> list[dict]:
        """
        Generic scraper doesn't support company-wide scraping.

        Returns a single-item list if the slug is a URL, otherwise empty.
        """
        if company_slug.startswith("http"):
            result = self.scrape_job(company_slug)
            return [result] if result else []
        return []

    def _parse_page(self, html_text: str, url: str) -> dict | None:
        """
        Parse HTML content to extract job information.

        Args:
            html_text: Raw HTML content.
            url: The page URL (for reference).

        Returns:
            Unified schema dict.
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.error("BeautifulSoup not installed. Cannot parse generic pages.")
            return self._fallback_from_url(url)

        try:
            soup = BeautifulSoup(html_text, "lxml")

            job = self._empty_job()
            job["source"] = "google_dork"
            job["ats_platform"] = None
            job["job_url"] = url

            # --- Extract title ---
            # Priority: og:title → h1 → title tag
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                job["title"] = og_title["content"].strip()
            else:
                h1 = soup.find("h1")
                if h1:
                    job["title"] = h1.get_text(strip=True)
                else:
                    title_tag = soup.find("title")
                    if title_tag:
                        job["title"] = title_tag.get_text(strip=True)

            # --- Extract company name from domain ---
            parsed = urlparse(url)
            domain = parsed.hostname or ""
            # Remove www. and TLD
            domain_parts = domain.replace("www.", "").split(".")
            if domain_parts:
                company_name = domain_parts[0]
                # Clean up
                company_name = re.sub(r"[-_]", " ", company_name).title()
                job["company"] = company_name

            # Try og:site_name for company
            og_site = soup.find("meta", property="og:site_name")
            if og_site and og_site.get("content"):
                job["company"] = og_site["content"].strip()

            # --- Extract description ---
            # Try structured data first
            desc_text = ""

            # Look for common job description containers
            desc_selectors = [
                ".job-description",
                ".job-details",
                ".job-content",
                ".position-description",
                ".careers-description",
                "#job-description",
                "#job-details",
                "[itemprop='description']",
                "article",
                ".content",
                "main",
            ]

            for selector in desc_selectors:
                desc_elem = soup.select_one(selector)
                if desc_elem:
                    desc_text = desc_elem.get_text(separator="\n", strip=True)
                    if len(desc_text) > 100:  # Minimum meaningful content
                        break

            if not desc_text or len(desc_text) < 100:
                # Fallback: get body text
                body = soup.find("body")
                if body:
                    # Remove nav, header, footer, script, style
                    for tag in body.find_all(["nav", "header", "footer", "script", "style", "noscript"]):
                        tag.decompose()
                    desc_text = body.get_text(separator="\n", strip=True)

            # Limit description length
            if desc_text:
                job["description"] = desc_text[:5000]

            # --- Extract location ---
            # Try structured data
            loc_selectors = [
                ".job-location",
                ".location",
                "[itemprop='jobLocation']",
                "[itemprop='addressLocality']",
            ]
            for selector in loc_selectors:
                loc_elem = soup.select_one(selector)
                if loc_elem:
                    job["location"] = loc_elem.get_text(strip=True)
                    break

            # --- Check for remote ---
            page_text = html_text.lower()
            if "remote" in (job.get("title") or "").lower() or "remote" in (job.get("location") or "").lower():
                job["is_remote"] = True

            # --- Try to extract date ---
            date_selectors = [
                "[itemprop='datePosted']",
                ".date-posted",
                ".posting-date",
                "time",
            ]
            for selector in date_selectors:
                date_elem = soup.select_one(selector)
                if date_elem:
                    date_text = date_elem.get("datetime") or date_elem.get("content") or date_elem.get_text(strip=True)
                    if date_text and len(date_text) >= 10:
                        job["date_posted"] = date_text[:10]
                        break

            # --- Extract structured data (JSON-LD) ---
            json_ld = self._extract_json_ld(soup)
            if json_ld:
                if not job.get("title") and json_ld.get("title"):
                    job["title"] = json_ld["title"]
                if not job.get("company") and json_ld.get("hiringOrganization"):
                    org = json_ld["hiringOrganization"]
                    if isinstance(org, dict):
                        job["company"] = org.get("name", job.get("company"))
                if json_ld.get("datePosted"):
                    job["date_posted"] = str(json_ld["datePosted"])[:10]
                if json_ld.get("jobLocation"):
                    loc = json_ld["jobLocation"]
                    if isinstance(loc, dict):
                        address = loc.get("address", {})
                        if isinstance(address, dict):
                            city = address.get("addressLocality", "")
                            country = address.get("addressCountry", "")
                            if city:
                                job["location"] = city
                            if country:
                                job["country"] = country

            return job

        except Exception as e:
            logger.error("Error parsing generic page HTML for %s: %s", url, e)
            return self._fallback_from_url(url)

    def _extract_json_ld(self, soup) -> dict | None:
        """Extract JobPosting schema from JSON-LD structured data."""
        try:
            import json
            scripts = soup.find_all("script", type="application/ld+json")
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                                return item
                    elif isinstance(data, dict):
                        if data.get("@type") == "JobPosting":
                            return data
                        # Check @graph
                        graph = data.get("@graph", [])
                        for item in graph:
                            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                                return item
                except (json.JSONDecodeError, TypeError):
                    continue
        except Exception:
            pass
        return None

    def _fallback_from_url(self, url: str) -> dict | None:
        """Create a minimal job entry from just the URL."""
        job = self._empty_job()
        job["source"] = "google_dork"
        job["ats_platform"] = None
        job["job_url"] = url

        # Extract company from domain
        try:
            parsed = urlparse(url)
            domain = (parsed.hostname or "").replace("www.", "")
            parts = domain.split(".")
            if parts:
                job["company"] = parts[0].replace("-", " ").replace("_", " ").title()
        except Exception:
            pass

        # Try to extract title from URL path
        try:
            path = urlparse(url).path
            segments = [s for s in path.strip("/").split("/") if s]
            for seg in reversed(segments):
                if len(seg) > 3 and not seg.isdigit():
                    job["title"] = seg.replace("-", " ").replace("_", " ").title()
                    break
        except Exception:
            pass

        return job


# Module-level instance
_scraper = GenericScraper()


def scrape_generic(url: str) -> dict | None:
    """Convenience: scrape a single generic career page."""
    return _scraper.scrape_job(url)
