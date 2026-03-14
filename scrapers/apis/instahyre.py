"""
scrapers/apis/instahyre.py — Instahyre.com job scraper.

Scrapes job listings from Instahyre.com's public job listing pages.
Instahyre is a popular curated tech job platform in India.
"""

import logging
import random
import re
from typing import Callable

import requests
from bs4 import BeautifulSoup

from config import USER_AGENTS, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

BASE_URL = "https://www.instahyre.com"


def scrape_instahyre(
    search_term: str = "",
    search_terms: list[str] | None = None,
    location: str = "",
    search_locations: list[str] | None = None,
    max_pages: int = 3,
    progress_callback: Callable[[str], None] | None = None,
) -> list[dict]:
    """Scrape jobs from Instahyre.com.

    Args:
        search_term: Single search keyword (legacy).
        search_terms: List of job titles to search for.
        location: Location to filter by.
        search_locations: List of locations for broader scope.
        max_pages: Maximum pages to fetch per search term.
        progress_callback: Optional progress updates.

    Returns:
        List of dicts matching the unified job schema.
    """
    if search_terms:
        terms_list = search_terms
    elif search_term:
        terms_list = [search_term]
    else:
        terms_list = []

    loc = location
    if not loc and search_locations:
        loc = search_locations[0]

    if progress_callback:
        progress_callback(f"Instahyre: Searching for {len(terms_list)} roles in '{loc}'...")

    all_jobs: list[dict] = []

    for term in terms_list:
        try:
            jobs = _search_instahyre(term, loc, max_pages, progress_callback)
            all_jobs.extend(jobs)
        except Exception as e:
            logger.warning("Instahyre search failed for '%s': %s", term, e)
            if progress_callback:
                progress_callback(f"Instahyre: Error searching '{term}': {str(e)[:60]}")

    if progress_callback:
        progress_callback(f"Instahyre: {len(all_jobs)} total jobs found.")

    return all_jobs


def _search_instahyre(
    search_term: str,
    location: str,
    max_pages: int,
    progress_callback: Callable[[str], None] | None,
) -> list[dict]:
    """Search Instahyre for a single term."""
    jobs: list[dict] = []
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html, application/xhtml+xml, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.instahyre.com/",
    }

    # Instahyre uses slug-based URLs for job listings
    term_slug = search_term.lower().replace(" ", "-")
    loc_slug = location.lower().replace(" ", "-").replace(",", "") if location else ""

    for page in range(1, max_pages + 1):
        try:
            if loc_slug:
                search_url = f"{BASE_URL}/search-jobs/?job_title={term_slug}&location={loc_slug}&page={page}"
            else:
                search_url = f"{BASE_URL}/search-jobs/?job_title={term_slug}&page={page}"

            resp = requests.get(
                search_url,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )

            if resp.status_code != 200:
                logger.debug("Instahyre page %d returned %d", page, resp.status_code)
                break

            page_jobs = _parse_instahyre_html(resp.text)
            if not page_jobs:
                break

            jobs.extend(page_jobs)
            logger.info("Instahyre: page %d -> %d jobs for '%s'", page, len(page_jobs), search_term)

        except Exception as e:
            logger.warning("Instahyre page %d failed: %s", page, e)
            break

    return jobs


def _parse_instahyre_html(html: str) -> list[dict]:
    """Parse Instahyre search results HTML into job dicts."""
    jobs: list[dict] = []

    try:
        soup = BeautifulSoup(html, "lxml")

        job_cards = soup.select(".job-card, .opportunity-card, [data-opportunity-id]")

        if not job_cards:
            job_cards = soup.find_all("div", class_=re.compile(r"job[-_]?card|opportunity", re.I))

        for card in job_cards:
            try:
                title_el = card.select_one("h3 a, .job-title a, .opportunity-title a, a[data-job-title]")
                title = title_el.get_text(strip=True) if title_el else None

                company_el = card.select_one(".company-name, .employer-name, a[data-company]")
                company = company_el.get_text(strip=True) if company_el else None

                location_el = card.select_one(".location, .job-location, .city")
                loc = location_el.get_text(strip=True) if location_el else None

                url = None
                if title_el and title_el.get("href"):
                    url = title_el["href"]
                    if url and not url.startswith("http"):
                        url = f"{BASE_URL}{url}"

                desc_el = card.select_one(".job-description, .desc, .skills")
                description = desc_el.get_text(strip=True) if desc_el else ""

                salary_el = card.select_one(".salary, .compensation, .ctc")
                salary_text = salary_el.get_text(strip=True) if salary_el else ""
                salary_min, salary_max = _parse_salary(salary_text)

                exp_el = card.select_one(".experience, .exp")

                if not title or not url:
                    continue

                is_remote = False
                if loc and "remote" in loc.lower():
                    is_remote = True
                if title and "remote" in title.lower():
                    is_remote = True

                job = {
                    "source": "instahyre",
                    "ats_platform": None,
                    "title": title,
                    "company": company,
                    "location": loc,
                    "country": "India",
                    "date_posted": None,
                    "job_type": "fulltime",
                    "is_remote": is_remote,
                    "salary_min": salary_min,
                    "salary_max": salary_max,
                    "salary_currency": "INR" if (salary_min or salary_max) else None,
                    "salary_interval": "yearly" if (salary_min or salary_max) else None,
                    "job_url": url,
                    "company_url": None,
                    "description": description,
                    "language": None,
                    "ai_score": None,
                    "ai_reasoning": None,
                    "ai_cover_letter": None,
                    "ai_resume_bullets": None,
                }
                jobs.append(job)

            except Exception as e:
                logger.debug("Error parsing Instahyre job card: %s", e)
                continue

    except Exception as e:
        logger.warning("Instahyre HTML parsing failed: %s", e)

    return jobs


def _parse_salary(salary_text: str) -> tuple[float | None, float | None]:
    """Parse salary range from text like '15-25 LPA' or '10L - 20L'."""
    if not salary_text:
        return None, None

    numbers = re.findall(r"(\d+(?:\.\d+)?)", salary_text)
    if not numbers:
        return None, None

    multiplier = 1.0
    text_lower = salary_text.lower()
    if "lpa" in text_lower or "lac" in text_lower or "lakh" in text_lower or "l" in text_lower:
        multiplier = 100000.0
    elif "cr" in text_lower or "crore" in text_lower:
        multiplier = 10000000.0

    try:
        if len(numbers) >= 2:
            return float(numbers[0]) * multiplier, float(numbers[1]) * multiplier
        elif len(numbers) == 1:
            return float(numbers[0]) * multiplier, None
    except (ValueError, IndexError):
        pass

    return None, None
