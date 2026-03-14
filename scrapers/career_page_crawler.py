"""
scrapers/career_page_crawler.py — Hidden job discovery via company career pages.

Given a company domain, discovers the career/jobs page by:
1. Checking robots.txt for sitemap references
2. Parsing sitemap.xml for /careers or /jobs paths
3. Probing common career URL patterns
4. Auto-detecting which ATS platform the career page uses
5. Routing to existing ATS scrapers when a known platform is found

Also supports bulk discovery from job results: extracts company domains
from existing jobs and crawls their career pages for additional listings.
"""

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable
from urllib.parse import urljoin, urlparse

import requests

from config import ATS_PATTERNS, USER_AGENTS, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

CAREER_PATH_PATTERNS = [
    "/careers",
    "/jobs",
    "/careers/",
    "/jobs/",
    "/en/careers",
    "/en/jobs",
    "/about/careers",
    "/company/careers",
    "/work-with-us",
    "/join-us",
    "/open-positions",
    "/vacancies",
    "/opportunities",
]

ATS_DETECTION_PATTERNS = {
    "greenhouse": [
        r"boards\.greenhouse\.io/([\w-]+)",
        r"greenhouse\.io",
        r"grnh\.se",
    ],
    "lever": [
        r"jobs\.lever\.co/([\w-]+)",
        r"lever\.co",
    ],
    "ashby": [
        r"jobs\.ashbyhq\.com/([\w-]+)",
        r"ashbyhq\.com",
    ],
    "workday": [
        r"[\w-]+\.wd\d+\.myworkdayjobs\.com",
        r"myworkdayjobs\.com",
    ],
    "personio": [
        r"([\w-]+)\.jobs\.personio\.de",
        r"personio\.de",
    ],
    "smartrecruiters": [
        r"jobs\.smartrecruiters\.com/([\w-]+)",
        r"smartrecruiters\.com",
    ],
    "icims": [
        r"careers[\w-]*\.icims\.com",
        r"icims\.com",
    ],
    "taleo": [
        r"[\w-]+\.taleo\.net",
        r"taleo\.net",
    ],
    "bamboohr": [
        r"([\w-]+)\.bamboohr\.com/careers",
        r"bamboohr\.com",
    ],
    "recruitee": [
        r"([\w-]+)\.recruitee\.com",
        r"recruitee\.com",
    ],
    "breezyhr": [
        r"([\w-]+)\.breezy\.hr",
        r"breezy\.hr",
    ],
}


def _get_with_timeout(url: str, timeout: int = 10) -> requests.Response | None:
    """GET request with short timeout for probing."""
    try:
        import random
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html, application/xml, application/json, */*",
        }
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        if resp.status_code < 400:
            return resp
    except Exception:
        pass
    return None


def detect_ats_from_url(url: str) -> tuple[str | None, str | None]:
    """Detect ATS platform and extract slug from a URL.

    Returns (ats_name, slug) or (None, None).
    """
    for ats_name, patterns in ATS_DETECTION_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                slug = match.group(1) if match.lastindex else None
                return ats_name, slug
    return None, None


def detect_ats_from_page(html: str, base_url: str) -> tuple[str | None, str | None]:
    """Detect ATS platform from page HTML content by looking for embedded links/iframes."""
    for ats_name, patterns in ATS_DETECTION_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                slug = match.group(1) if match.lastindex else None
                return ats_name, slug
    return None, None


def discover_career_page(domain: str) -> dict | None:
    """Discover the career page for a company domain.

    Returns a dict with keys: career_url, ats, slug, or None if not found.
    """
    base = f"https://{domain}" if not domain.startswith("http") else domain
    parsed = urlparse(base)
    domain_clean = parsed.netloc or parsed.path.split("/")[0]
    base = f"https://{domain_clean}"

    # Step 1: Check robots.txt for sitemap
    sitemap_urls = _find_sitemaps_from_robots(base)

    # Step 2: Check sitemaps for career pages
    for sitemap_url in sitemap_urls[:3]:
        career_url = _find_career_in_sitemap(sitemap_url)
        if career_url:
            ats, slug = detect_ats_from_url(career_url)
            return {"career_url": career_url, "ats": ats, "slug": slug, "domain": domain_clean}

    # Step 3: Probe common career URL patterns
    for path in CAREER_PATH_PATTERNS:
        probe_url = urljoin(base, path)
        resp = _get_with_timeout(probe_url, timeout=8)
        if resp:
            final_url = resp.url
            ats, slug = detect_ats_from_url(final_url)
            if ats:
                return {"career_url": final_url, "ats": ats, "slug": slug, "domain": domain_clean}

            ats, slug = detect_ats_from_page(resp.text[:50000], final_url)
            if ats:
                return {"career_url": final_url, "ats": ats, "slug": slug, "domain": domain_clean}

            if _looks_like_career_page(resp.text):
                return {"career_url": final_url, "ats": None, "slug": None, "domain": domain_clean}

    return None


def _find_sitemaps_from_robots(base_url: str) -> list[str]:
    """Parse robots.txt for Sitemap directives."""
    sitemaps = []
    resp = _get_with_timeout(f"{base_url}/robots.txt", timeout=8)
    if resp:
        for line in resp.text.splitlines():
            if line.strip().lower().startswith("sitemap:"):
                url = line.split(":", 1)[1].strip()
                sitemaps.append(url)

    default_sitemap = f"{base_url}/sitemap.xml"
    if default_sitemap not in sitemaps:
        sitemaps.append(default_sitemap)

    return sitemaps


def _find_career_in_sitemap(sitemap_url: str) -> str | None:
    """Look for career/jobs URLs in a sitemap."""
    resp = _get_with_timeout(sitemap_url, timeout=10)
    if not resp:
        return None

    career_keywords = ["career", "jobs", "vacancies", "openings", "join", "hiring"]
    for line in resp.text.splitlines():
        loc_match = re.search(r"<loc>(.*?)</loc>", line)
        if loc_match:
            url = loc_match.group(1)
            url_lower = url.lower()
            if any(kw in url_lower for kw in career_keywords):
                return url
    return None


def _looks_like_career_page(html: str) -> bool:
    """Heuristic: does this HTML look like a career/jobs page?"""
    html_lower = html.lower()
    career_signals = [
        "open positions", "current openings", "job openings",
        "career opportunities", "join our team", "we're hiring",
        "apply now", "view all jobs", "search jobs",
        "open roles", "job listings",
    ]
    matches = sum(1 for signal in career_signals if signal in html_lower)
    return matches >= 2


def crawl_career_pages(
    domains: list[str],
    search_terms: list[str],
    loc_filters: list[str] | None = None,
    max_workers: int = 10,
    max_domains: int = 50,
    progress_callback: Callable[[str], None] | None = None,
) -> list[dict]:
    """Discover and scrape career pages for a list of company domains.

    Args:
        domains: List of company domains to check.
        search_terms: Job titles to filter by.
        loc_filters: Location strings to filter by.
        max_workers: Concurrent threads.
        max_domains: Max domains to check.
        progress_callback: Optional progress updates.

    Returns:
        List of job dicts in unified schema.
    """
    def _cb(msg):
        logger.info(msg)
        if progress_callback:
            try:
                progress_callback(msg)
            except Exception:
                pass

    _cb(f"Career Page Crawler: Checking {min(len(domains), max_domains)} company domains...")

    all_jobs: list[dict] = []
    discovered = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for domain in domains[:max_domains]:
            futures[executor.submit(
                _discover_and_scrape_one, domain, search_terms, loc_filters or []
            )] = domain

        for future in as_completed(futures):
            domain = futures[future]
            try:
                result = future.result(timeout=30)
                if result:
                    all_jobs.extend(result)
                    discovered += 1
                    _cb(f"  Career Crawler: {domain} -> {len(result)} matching jobs")
            except Exception as e:
                logger.debug("Career crawl failed for %s: %s", domain, e)

    _cb(f"Career Page Crawler: {len(all_jobs)} jobs from {discovered} company sites")
    return all_jobs


def _discover_and_scrape_one(
    domain: str, search_terms: list[str], loc_filters: list[str]
) -> list[dict]:
    """Discover career page for one domain and scrape matching jobs."""
    time.sleep(0.3)

    result = discover_career_page(domain)
    if not result:
        return []

    ats = result.get("ats")
    slug = result.get("slug")

    if not ats or not slug:
        return []

    try:
        if ats == "greenhouse":
            from scrapers.ats.greenhouse import scrape_greenhouse_company
            all_jobs = scrape_greenhouse_company(slug, search_term=None, location=None)
        elif ats == "lever":
            from scrapers.ats.lever import scrape_lever_company
            all_jobs = scrape_lever_company(slug, search_term=None, location=None)
        elif ats == "ashby":
            from scrapers.ats.ashby import scrape_ashby_company
            all_jobs = scrape_ashby_company(slug, search_term=None, location=None)
        elif ats == "smartrecruiters":
            from scrapers.ats.smartrecruiters import scrape_sr_company
            all_jobs = scrape_sr_company(slug, search_term=None, location=None)
        elif ats == "personio":
            from scrapers.ats.personio import scrape_personio_company
            all_jobs = scrape_personio_company(slug, search_term=None, location=None)
        else:
            return []
    except Exception as e:
        logger.debug("ATS scrape failed for %s (%s:%s): %s", domain, ats, slug, e)
        return []

    if not all_jobs:
        return []

    matched = []
    search_terms_lower = [t.lower() for t in search_terms]

    for job in all_jobs:
        title = (job.get("title") or "").lower()
        desc = (job.get("description") or "").lower()

        term_match = False
        for term in search_terms_lower:
            words = term.split()
            if all(w in title for w in words):
                term_match = True
                break
            if all(w in desc for w in words):
                term_match = True
                break

        if not term_match:
            continue

        if loc_filters:
            job_loc = (job.get("location") or "").lower()
            if not any(loc in job_loc for loc in loc_filters) and "remote" not in job_loc:
                continue

        job["source"] = "career_crawler"
        matched.append(job)

    return matched


def extract_domains_from_jobs(jobs: list[dict]) -> list[str]:
    """Extract unique company domains from job URLs for further crawling."""
    domains = set()
    for job in jobs:
        company_url = job.get("company_url") or ""
        job_url = job.get("job_url") or ""

        for url in [company_url, job_url]:
            if not url or not url.startswith("http"):
                continue
            try:
                parsed = urlparse(url)
                domain = parsed.netloc.lower()
                domain = re.sub(r"^www\.", "", domain)
                # Skip known job board domains
                skip_domains = {
                    "indeed.com", "linkedin.com", "glassdoor.com",
                    "google.com", "ziprecruiter.com", "naukri.com",
                    "foundit.in", "instahyre.com", "arbeitnow.com",
                    "boards.greenhouse.io", "jobs.lever.co",
                    "jobs.ashbyhq.com", "jobs.smartrecruiters.com",
                }
                if not any(skip in domain for skip in skip_domains):
                    domains.add(domain)
            except Exception:
                continue

    return list(domains)
