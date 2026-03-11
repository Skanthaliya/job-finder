"""
scrapers/url_router.py — URL classifier and ATS scraper dispatcher.

Takes a list of discovered URLs (from Google dorking), matches each against
known ATS URL patterns, and dispatches to the correct ATS scraper.

Key optimization: For Greenhouse and Lever, discovering ONE job URL triggers
fetching ALL jobs for that company via their API.
"""

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Callable

from config import ATS_PATTERNS

logger = logging.getLogger(__name__)


def route_and_scrape(
    urls: list[str],
    search_terms: list[str] | str | None = None,
    location: str | None = None,
    max_workers: int = 5,
    progress_callback: Callable[[str], None] | None = None,
) -> list[dict]:
    """
    Classify discovered URLs by ATS type and dispatch to correct scrapers.

    For Greenhouse and Lever, extracts the company slug and fetches ALL jobs
    for that company, not just the single discovered URL. Keeps track of
    already-scraped companies to avoid duplicates.

    Args:
        urls: List of discovered URLs.
        search_terms: Optional keyword filter(s) for ATS company scraping.
        location: Optional location filter.
        max_workers: Maximum concurrent scraping threads.
        progress_callback: Optional function for progress updates.

    Returns:
        List of unified schema dicts.
    """
    if not urls:
        return []

    # Normalize search_terms to list
    if isinstance(search_terms, str):
        search_terms = [search_terms] if search_terms else []
    elif search_terms is None:
        search_terms = []

    logger.info("URL Router: Classifying and routing %d URLs...", len(urls))

    # Filter out junk URLs that aren't actual job postings
    original_count = len(urls)
    urls = _filter_valid_job_urls(urls)
    if len(urls) < original_count:
        logger.info("URL Router: Filtered %d junk URLs, %d valid remaining", 
                    original_count - len(urls), len(urls))

    # Auto-save all discovered company slugs to registry
    from scrapers.company_registry import load_registry, save_registry, extract_ats_from_url

    registry = load_registry()
    new_discovered = 0
    for url in urls:
        result = extract_ats_from_url(url)
        if result:
            ats, slug = result
            key = f"{ats}:{slug}"
            if key not in registry["companies"]:
                entry = {
                    "ats": ats,
                    "slug": slug,
                    "company_name": slug.replace("-", " ").title(),
                    "discovered_from": "serpapi",
                    "discovered_date": datetime.now().isoformat(),
                }
                if ats == "workday":
                    entry["url"] = url
                registry["companies"][key] = entry
                new_discovered += 1

    if new_discovered > 0:
        save_registry(registry)
        logger.info("URL Router: Auto-saved %d new companies to registry", new_discovered)
        if progress_callback:
            try:
                progress_callback(f"URL Router: Discovered {new_discovered} new companies for future searches!")
            except Exception:
                pass

    # Classify URLs
    classified: dict[str, list[dict]] = {
        "greenhouse": [],
        "lever": [],
        "workday": [],
        "personio": [],
        "ashby": [],
        "smartrecruiters": [],
        "generic": [],
    }

    for url in urls:
        ats_type, slug_or_url = _classify_url(url)
        classified[ats_type].append({"url": url, "slug": slug_or_url})

    # Log classification summary
    summary = {k: len(v) for k, v in classified.items() if v}
    logger.info("URL classification: %s", summary)
    if progress_callback:
        progress_callback(f"URL Router: {summary}")

    all_jobs: list[dict] = []
    scraped_companies: set[str] = set()  # Track scraped company slugs

    # Use ThreadPoolExecutor for parallel scraping
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}

        # --- Greenhouse (company-wide scraping) ---
        for item in classified.get("greenhouse", []):
            slug = item["slug"]
            if slug and slug not in scraped_companies:
                scraped_companies.add(slug)
                futures[executor.submit(
                    _scrape_greenhouse_company, slug, search_terms, location
                )] = f"greenhouse:{slug}"

        # --- Lever (company-wide scraping) ---
        for item in classified.get("lever", []):
            slug = item["slug"]
            if slug and slug not in scraped_companies:
                scraped_companies.add(slug)
                futures[executor.submit(
                    _scrape_lever_company, slug, search_terms, location
                )] = f"lever:{slug}"

        # --- Ashby (company-wide scraping) ---
        for item in classified.get("ashby", []):
            slug = item["slug"]
            if slug and slug not in scraped_companies:
                scraped_companies.add(slug)
                futures[executor.submit(
                    _scrape_ashby_company, slug, search_terms, location
                )] = f"ashby:{slug}"

        # --- SmartRecruiters (company-wide scraping) ---
        for item in classified.get("smartrecruiters", []):
            slug = item["slug"]
            if slug and slug not in scraped_companies:
                scraped_companies.add(slug)
                futures[executor.submit(
                    _scrape_sr_company, slug, search_terms, location
                )] = f"smartrecruiters:{slug}"

        # --- Workday (per-URL scraping, company-wide where possible) ---
        workday_urls_handled: set[str] = set()
        for item in classified.get("workday", []):
            url = item["url"]
            if url not in workday_urls_handled:
                workday_urls_handled.add(url)
                futures[executor.submit(
                    _scrape_workday_job, url, search_terms, location
                )] = f"workday:{url[:60]}"

        # --- Personio (per-company if slug extractable) ---
        personio_handled: set[str] = set()
        for item in classified.get("personio", []):
            slug = item["slug"]
            url = item["url"]
            if slug and slug not in personio_handled:
                personio_handled.add(slug)
                futures[executor.submit(
                    _scrape_personio_company, slug, search_terms, location
                )] = f"personio:{slug}"
            elif not slug and url not in personio_handled:
                personio_handled.add(url)
                futures[executor.submit(
                    _scrape_personio_job, url, search_terms, location
                )] = f"personio:{url[:60]}"

        # --- Generic (individual URL scraping, limited) ---
        generic_count = 0
        max_generic = 20  # Limit generic scraping to avoid slowdowns
        for item in classified.get("generic", []):
            if generic_count >= max_generic:
                break
            url = item["url"]
            futures[executor.submit(_scrape_generic, url)] = f"generic:{url[:60]}"
            generic_count += 1

        # Collect results
        completed = 0
        total_futures = len(futures)

        for future in as_completed(futures):
            completed += 1
            label = futures[future]
            try:
                result = future.result(timeout=60)
                if result:
                    if isinstance(result, list):
                        all_jobs.extend(result)
                        logger.info("  %s: %d jobs", label, len(result))
                    elif isinstance(result, dict):
                        all_jobs.append(result)
                        logger.info("  %s: 1 job", label)
                else:
                    logger.debug("  %s: no results", label)
            except Exception as e:
                logger.warning("  %s failed: %s", label, e)

            if progress_callback and completed % 5 == 0:
                progress_callback(f"ATS scraping: {completed}/{total_futures} tasks done, {len(all_jobs)} jobs so far...")

    logger.info("URL Router: %d total jobs scraped from %d URLs.", len(all_jobs), len(urls))
    if progress_callback:
        progress_callback(f"ATS scraping complete: {len(all_jobs)} jobs from {len(urls)} URLs.")

    return all_jobs


def _classify_url(url: str) -> tuple[str, str | None]:
    """
    Classify a URL by matching against known ATS patterns.

    Returns: (ats_type, company_slug_or_url)
    """
    for ats_type, pattern in ATS_PATTERNS.items():
        match = re.search(pattern, url)
        if match:
            # Extract company slug from first capture group if available
            slug = match.group(1) if match.lastindex and match.lastindex >= 1 else None
            return ats_type, slug

    return "generic", None


# =============================================================================
# Safe scraper wrappers (each catches its own exceptions)
# =============================================================================

def _scrape_greenhouse_company(slug: str, search_terms: list[str], location: str | None) -> list[dict]:
    """Safely scrape a Greenhouse company."""
    try:
        from scrapers.ats.greenhouse import scrape_greenhouse_company
        time.sleep(1)
        all_jobs = scrape_greenhouse_company(slug, search_term=None, location=None)
        if not all_jobs:
            return []
        return _filter_by_terms_and_location(all_jobs, search_terms, location)
    except Exception as e:
        logger.error("Greenhouse scrape failed for %s: %s", slug, e)
        return []


def _scrape_lever_company(slug: str, search_terms: list[str], location: str | None) -> list[dict]:
    """Safely scrape a Lever company."""
    try:
        from scrapers.ats.lever import scrape_lever_company
        time.sleep(1)
        all_jobs = scrape_lever_company(slug, search_term=None, location=None)
        if not all_jobs:
            return []
        return _filter_by_terms_and_location(all_jobs, search_terms, location)
    except Exception as e:
        logger.error("Lever scrape failed for %s: %s", slug, e)
        return []


def _scrape_ashby_company(slug: str, search_terms: list[str], location: str | None) -> list[dict]:
    """Safely scrape an Ashby company."""
    try:
        from scrapers.ats.ashby import scrape_ashby_company
        time.sleep(1)
        all_jobs = scrape_ashby_company(slug, search_term=None, location=None)
        if not all_jobs:
            return []
        return _filter_by_terms_and_location(all_jobs, search_terms, location)
    except Exception as e:
        logger.error("Ashby scrape failed for %s: %s", slug, e)
        return []


def _scrape_sr_company(slug: str, search_terms: list[str], location: str | None) -> list[dict]:
    """Safely scrape a SmartRecruiters company."""
    try:
        from scrapers.ats.smartrecruiters import scrape_sr_company
        time.sleep(1)
        all_jobs = scrape_sr_company(slug, search_term=None, location=None)
        if not all_jobs:
            return []
        return _filter_by_terms_and_location(all_jobs, search_terms, location)
    except Exception as e:
        logger.error("SmartRecruiters scrape failed for %s: %s", slug, e)
        return []


def _scrape_workday_job(url: str, search_terms: list[str], location: str | None) -> dict | None:
    """Safely scrape a Workday job."""
    try:
        from scrapers.ats.workday import scrape_workday_job
        time.sleep(0.5)
        job = scrape_workday_job(url)
        if job:
            filtered = _filter_by_terms_and_location([job], search_terms, location)
            return filtered[0] if filtered else None
        return None
    except Exception as e:
        logger.error("Workday scrape failed for %s: %s", url, e)
        return None


def _scrape_personio_company(slug: str, search_terms: list[str], location: str | None) -> list[dict]:
    """Safely scrape a Personio company."""
    try:
        from scrapers.ats.personio import scrape_personio_company
        time.sleep(1)
        all_jobs = scrape_personio_company(slug, search_term=None, location=None)
        if not all_jobs:
            return []
        return _filter_by_terms_and_location(all_jobs, search_terms, location)
    except Exception as e:
        logger.error("Personio scrape failed for %s: %s", slug, e)
        return []


def _scrape_personio_job(url: str, search_terms: list[str], location: str | None) -> dict | None:
    """Safely scrape a single Personio job."""
    try:
        from scrapers.ats.personio import scrape_personio_job
        time.sleep(0.5)
        job = scrape_personio_job(url)
        if job:
            filtered = _filter_by_terms_and_location([job], search_terms, location)
            return filtered[0] if filtered else None
        return None
    except Exception as e:
        logger.error("Personio job scrape failed for %s: %s", url, e)
        return None


def _scrape_generic(url: str) -> dict | None:
    """Safely scrape a generic career page."""
    try:
        from scrapers.ats.generic import scrape_generic
        time.sleep(0.5)
        return scrape_generic(url)
    except Exception as e:
        logger.error("Generic scrape failed for %s: %s", url, e)
        return None


def _filter_by_terms_and_location(
    jobs: list[dict], search_terms: list[str], location: str | None
) -> list[dict]:
    """Filter jobs by multiple search terms and location."""
    if not search_terms and not location:
        return jobs

    terms_lower = [t.lower() for t in search_terms] if search_terms else []
    loc_lower = location.lower() if location else ""

    matched = []
    for job in jobs:
        title = (job.get("title") or "").lower()
        desc = (job.get("description") or "").lower()

        # Check search terms (if any)
        if terms_lower:
            term_match = False
            for term in terms_lower:
                words = term.split()
                if all(w in title for w in words):
                    term_match = True
                    break
                if all(w in desc for w in words):
                    term_match = True
                    break
            if not term_match:
                continue

        # Check location (if set)
        if loc_lower:
            job_loc = (job.get("location") or "").lower()
            if loc_lower not in job_loc and "remote" not in job_loc:
                continue

        matched.append(job)

    return matched


# Domains that are NOT actual job postings
BLOCKED_DOMAINS = [
    "facebook.com", "twitter.com", "x.com", "instagram.com", "tiktok.com",
    "youtube.com", "reddit.com", "quora.com",
    "linkedin.com/feed", "linkedin.com/posts", "linkedin.com/pulse",
    "ziprecruiter.com/Jobs/", "ziprecruiter.com/jobs/",
    "indeed.com/q-", "indeed.com/jobs?", "indeed.com/career",
    "glassdoor.com/Job-", "glassdoor.com/job-listing",
    "jobright.ai", "adzuna.com", "jooble.org", "talent.com",
    "salary.com", "payscale.com", "levels.fyi",
    "wikipedia.org", "medium.com", "substack.com",
    "github.com", "stackoverflow.com", "stackexchange.com",
    "crunchbase.com", "pitchbook.com",
    "visa.co.uk/careers.html", "visa.com/careers.html",
]

# URL patterns that indicate an actual ATS job page
VALID_ATS_PATTERNS = [
    "myworkdayjobs.com",
    "boards.greenhouse.io",
    "jobs.lever.co",
    "jobs.ashbyhq.com",
    "jobs.personio.de",
    "jobs.smartrecruiters.com",
    "icims.com",
    "taleo.net",
    "breezy.hr",
    "recruiting.paylocity.com",
    "/job/", "/jobs/", "/career/", "/careers/",
    "/position/", "/opening/", "/vacancy/",
    "/apply", "/posting",
    "job-board", "jobboard",
]


def _filter_valid_job_urls(urls: list[str]) -> list[str]:
    """Filter out URLs that aren't actual job postings."""
    valid = []
    for url in urls:
        url_lower = url.lower()

        # Block known non-job domains
        if any(domain in url_lower for domain in BLOCKED_DOMAINS):
            logger.debug("Filtered blocked URL: %s", url[:80])
            continue

        # Must match at least one valid ATS/job pattern
        if any(pattern in url_lower for pattern in VALID_ATS_PATTERNS):
            valid.append(url)
        else:
            logger.debug("Filtered non-job URL: %s", url[:80])

    return valid
