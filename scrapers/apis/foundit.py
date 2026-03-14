"""
scrapers/apis/foundit.py — Foundit.in (formerly Monster India) scraper.

Scrapes job listings from Foundit.in's public search API and maps
them to the unified job schema.
"""

import logging
import random
import re
from typing import Callable

import requests
from bs4 import BeautifulSoup

from config import USER_AGENTS, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.foundit.in/middleware/jobsearch"


def scrape_foundit(
    search_term: str = "",
    search_terms: list[str] | None = None,
    location: str = "",
    search_locations: list[str] | None = None,
    max_pages: int = 3,
    progress_callback: Callable[[str], None] | None = None,
) -> list[dict]:
    """Scrape jobs from Foundit.in (formerly Monster India).

    Uses the public search endpoint to fetch job listings.

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
        progress_callback(f"Foundit.in: Searching for {len(terms_list)} roles in '{loc}'...")

    all_jobs: list[dict] = []

    for term in terms_list:
        try:
            jobs = _search_foundit(term, loc, max_pages, progress_callback)
            all_jobs.extend(jobs)
        except Exception as e:
            logger.warning("Foundit.in search failed for '%s': %s", term, e)
            if progress_callback:
                progress_callback(f"Foundit.in: Error searching '{term}': {str(e)[:60]}")

    if progress_callback:
        progress_callback(f"Foundit.in: {len(all_jobs)} total jobs found.")

    return all_jobs


def _search_foundit(
    search_term: str,
    location: str,
    max_pages: int,
    progress_callback: Callable[[str], None] | None,
) -> list[dict]:
    """Search Foundit.in for a single term."""
    jobs: list[dict] = []
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json, text/html, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.foundit.in/",
    }

    for page in range(1, max_pages + 1):
        try:
            # Foundit.in uses a search URL pattern
            search_url = f"https://www.foundit.in/srp/results?searchId=&query={search_term}&locations={location}&page={page}"

            resp = requests.get(
                search_url,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )

            if resp.status_code != 200:
                logger.debug("Foundit.in page %d returned %d", page, resp.status_code)
                break

            page_jobs = _parse_foundit_html(resp.text, search_term)
            if not page_jobs:
                break

            jobs.extend(page_jobs)
            logger.info("Foundit.in: page %d -> %d jobs for '%s'", page, len(page_jobs), search_term)

        except Exception as e:
            logger.warning("Foundit.in page %d failed: %s", page, e)
            break

    return jobs


def _parse_foundit_html(html: str, search_term: str) -> list[dict]:
    """Parse Foundit.in search results HTML into job dicts."""
    jobs: list[dict] = []

    try:
        soup = BeautifulSoup(html, "lxml")

        job_cards = soup.select(".srpResultCardContainer, .card-apply-content, [data-job-id]")

        if not job_cards:
            job_cards = soup.find_all("div", class_=re.compile(r"job[-_]?card|srp[-_]?result", re.I))

        for card in job_cards:
            try:
                title_el = card.select_one("a.job-tittle, .jobTitle a, h2 a, .designation a, a[data-job-title]")
                title = title_el.get_text(strip=True) if title_el else None

                company_el = card.select_one(".company-name, .companyName, .comp-name, a[data-company-name]")
                company = company_el.get_text(strip=True) if company_el else None

                location_el = card.select_one(".loc, .location, .job-location, span[data-location]")
                loc = location_el.get_text(strip=True) if location_el else None

                url = None
                if title_el and title_el.get("href"):
                    url = title_el["href"]
                    if url and not url.startswith("http"):
                        url = f"https://www.foundit.in{url}"

                exp_el = card.select_one(".exp, .experience, .expwdth")
                salary_el = card.select_one(".salary, .sal, .salary-info")

                desc_el = card.select_one(".job-description, .desc, .job-desc")
                description = desc_el.get_text(strip=True) if desc_el else ""

                date_el = card.select_one(".posted-date, .date, .job-date")
                date_posted = date_el.get_text(strip=True) if date_el else None

                if not title or not url:
                    continue

                is_remote = False
                if loc and "remote" in loc.lower():
                    is_remote = True
                if title and "remote" in title.lower():
                    is_remote = True

                job = {
                    "source": "foundit",
                    "ats_platform": None,
                    "title": title,
                    "company": company,
                    "location": loc,
                    "country": "India",
                    "date_posted": date_posted,
                    "job_type": None,
                    "is_remote": is_remote,
                    "salary_min": None,
                    "salary_max": None,
                    "salary_currency": "INR",
                    "salary_interval": None,
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
                logger.debug("Error parsing Foundit.in job card: %s", e)
                continue

    except Exception as e:
        logger.warning("Foundit.in HTML parsing failed: %s", e)

    return jobs
