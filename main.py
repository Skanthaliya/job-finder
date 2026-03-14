"""
main.py — CLI entry point and main orchestrator for Job Finder.

Runs all enabled scrapers in parallel, merges results, deduplicates, detects
languages, and outputs to Excel or CSV.

Usage:
    python main.py
    python main.py --search "Product Owner" "Scrum Master" --location "Berlin" --results 15
    python main.py --search "Product Owner" --scope europe --results 10
"""

import argparse
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from config import (
    DEFAULT_SEARCH_TERM,
    DEFAULT_SEARCH_TERMS,
    DEFAULT_LOCATION,
    DEFAULT_COUNTRY,
    DEFAULT_HOURS_OLD,
    DEFAULT_RESULTS_PER_SITE,
    EUROPEAN_COUNTRIES,
    JOBSPY_SITES,
    LOG_FILE,
    LOG_LEVEL,
    SCRAPER_TIMEOUT,
)
from filtering.date_filter import filter_by_date
from filtering.language_filter import filter_by_language
from filtering.location_filter import filter_by_location

# Configure logging
def setup_logging() -> None:
    """Set up logging to both console and file."""
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return  # Already set up — prevent duplicate handlers

    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    log_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)

    root_logger.setLevel(log_level)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(console_handler)

    # File handler
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(file_handler)


logger = logging.getLogger(__name__)


def run_search(
    search_terms: list[str] | str = DEFAULT_SEARCH_TERMS,
    location: str = DEFAULT_LOCATION,
    search_locations: list[str] | None = None,
    country: str = DEFAULT_COUNTRY,
    hours_old: int = DEFAULT_HOURS_OLD,
    results_per_site: int = DEFAULT_RESULTS_PER_SITE,
    job_type: str | None = None,
    is_remote: bool = False,
    language_filter: str | None = None,
    listing_language_filter: str | None = None,
    enable_jobspy: bool = True,
    jobspy_sites: list[str] | None = None,
    enable_ats_discovery: bool = True,
    enable_arbeitnow: bool = True,
    enable_remotive: bool = False,
    enable_foundit: bool = False,
    enable_instahyre: bool = False,
    enable_career_crawler: bool = False,
    enable_serpapi: bool = False,
    serpapi_key: str = "",
    output_format: str = "excel",
    progress_callback: Callable[[str], None] | None = None,
) -> tuple[list[dict], str]:
    """
    Main orchestrator. Runs all enabled scrapers, merges, deduplicates, filters, and outputs.

    Args:
        search_terms: Job titles/keywords (list or single string).
        location: City or region.
        search_locations: List of locations for country/Europe scope.
        country: Country name.
        hours_old: Max age of job postings in hours.
        results_per_site: Max results per job board site.
        job_type: Filter by type ("fulltime", "parttime", "contract", "internship").
        is_remote: Only remote jobs.
        language_filter: "English", "German", or None for all.
        enable_jobspy: Enable python-jobspy scraper.
        jobspy_sites: List of sites for JobSpy.
        enable_ats_discovery: Enable direct ATS API discovery.
        enable_arbeitnow: Enable Arbeitnow API.
        enable_remotive: Enable Remotive API.
        enable_foundit: Enable Foundit.in (India) scraper.
        enable_instahyre: Enable Instahyre.com (India) scraper.
        enable_career_crawler: Enable career page discovery crawler.
        enable_serpapi: Enable SerpAPI-based dorking.
        serpapi_key: SerpAPI key (overrides env var).
        output_format: "excel" or "csv".
        progress_callback: Function to call with progress updates.

    Returns:
        Tuple of (list of job dicts, output filepath).
    """
    start_time = time.time()

    # Normalize search_terms to list
    if isinstance(search_terms, str):
        search_terms = [search_terms]

    # Safe progress wrapper
    def _progress(msg: str) -> None:
        """Send progress update to callback and logger."""
        logger.info(msg)
        if progress_callback:
            try:
                progress_callback(msg)
            except Exception as e:
                logger.debug("Progress callback failed: %s", e)

    terms_display = ", ".join(f"'{t}'" for t in search_terms)
    _progress(f"🔍 Starting job search: [{terms_display}] in '{location}', {country}")
    _progress(f"   Filters: hours_old={hours_old}, job_type={job_type}, remote={is_remote}, language={language_filter}")
    if search_locations:
        _progress(f"   Location scope: {len(search_locations)} locations")

    # Auto-update company lists from GitHub (weekly)
    try:
        from scrapers.company_list_updater import update_company_lists
        new_companies = update_company_lists(progress_callback=_progress)
        if new_companies > 0:
            _progress(f"📦 Updated company database: {new_companies} new companies added")
    except Exception as e:
        logger.debug("Company list update skipped: %s", e)

    all_jobs: list[dict] = []
    sources_used: list[str] = []

    # =========================================================================
    # 1. Run scrapers in parallel
    # =========================================================================
    futures = {}
    with ThreadPoolExecutor(max_workers=4) as executor:

        # --- JobSpy ---
        if enable_jobspy:
            sites = jobspy_sites or JOBSPY_SITES[:3]
            _progress(f"Launching JobSpy scraper ({', '.join(sites)})...")
            futures["jobspy"] = executor.submit(
                _run_jobspy_safe,
                search_terms, location, sites, hours_old, results_per_site,
                country, job_type, is_remote, _progress,
            )

        # --- Arbeitnow ---
        if enable_arbeitnow:
            _progress("Launching Arbeitnow API scraper...")
            futures["arbeitnow"] = executor.submit(
                _run_arbeitnow_safe,
                search_terms, location, search_locations, language_filter, _progress,
            )

        # --- Remotive ---
        if enable_remotive:
            _progress("Launching Remotive API scraper...")
            futures["remotive"] = executor.submit(
                _run_remotive_safe,
                search_terms, location, search_locations, _progress,
            )

        # --- ATS Discovery (replaces Google Dorking) ---
        if enable_ats_discovery:
            _progress("Launching ATS Discovery engine...")
            futures["ats_discovery"] = executor.submit(
                _run_ats_discovery_safe,
                search_terms, location, search_locations, hours_old, _progress,
            )

        # --- Foundit.in (India) ---
        if enable_foundit:
            _progress("Launching Foundit.in scraper...")
            futures["foundit"] = executor.submit(
                _run_foundit_safe,
                search_terms, location, search_locations, _progress,
            )

        # --- Instahyre (India) ---
        if enable_instahyre:
            _progress("Launching Instahyre scraper...")
            futures["instahyre"] = executor.submit(
                _run_instahyre_safe,
                search_terms, location, search_locations, _progress,
            )

        # --- SerpAPI Dorking (optional) ---
        if enable_serpapi:
            _progress("Launching SerpAPI Dorking...")
            futures["serpapi"] = executor.submit(
                _run_serpapi_safe,
                search_terms, location, serpapi_key, _progress,
                country, search_locations,
            )

        # Collect results
        for name, future in futures.items():
            try:
                result = future.result(timeout=SCRAPER_TIMEOUT)
                if result:
                    all_jobs.extend(result)
                    sources_used.append(name)
                    _progress(f"✅ {name}: {len(result)} jobs collected.")
                else:
                    _progress(f"⚠️ {name}: No results.")
            except Exception as e:
                _progress(f"❌ {name} failed: {e}")
                logger.error("Scraper %s failed: %s", name, e, exc_info=True)

    _progress(f"\n📊 Total raw results: {len(all_jobs)} from {len(sources_used)} sources")

    if not all_jobs:
        _progress("No jobs found. Try broadening your search criteria.")
        if output_format == "csv":
            from output.csv_writer import write_csv
            filepath = write_csv([])
        elif output_format == "json":
            from output.json_writer import write_json
            filepath = write_json([])
        else:
            from output.excel_writer import write_excel
            filepath = write_excel([])
        return [], filepath

    # =========================================================================
    # 2. Normalize
    # =========================================================================
    _progress("Normalizing job data...")
    from processing.normalizer import normalize_jobs
    all_jobs = normalize_jobs(all_jobs)

    # =========================================================================
    # 2.5 Filter by date (removes stale ATS Discovery results)
    # =========================================================================
    all_jobs = filter_by_date(all_jobs, hours_old, progress_callback=_progress)

    # =========================================================================
    # 3. Detect languages
    # =========================================================================
    _progress("Detecting job languages...")
    from processing.language_detector import detect_languages_batch
    all_jobs = detect_languages_batch(all_jobs)

    # =========================================================================
    # 4. Apply language filters
    # =========================================================================
    all_jobs = filter_by_language(all_jobs, language_filter, progress_callback=_progress)

    if listing_language_filter:
        from filtering.language_filter import filter_by_listing_language
        all_jobs = filter_by_listing_language(all_jobs, listing_language_filter, progress_callback=_progress)

    # =========================================================================
    # 4.5 Apply location filter (for Country/Europe scope)
    # =========================================================================
    all_jobs = filter_by_location(all_jobs, search_locations, progress_callback=_progress)

    # =========================================================================
    # 5. Deduplicate
    # =========================================================================
    _progress("Deduplicating results...")
    from processing.deduplicator import deduplicate
    all_jobs = deduplicate(all_jobs)
    _progress(f"After deduplication: {len(all_jobs)} unique jobs")

    # =========================================================================
    # 5.5 Career Page Crawler (discover hidden jobs from company domains)
    # =========================================================================
    if enable_career_crawler and all_jobs:
        try:
            _progress("Career Crawler: Extracting company domains from results...")
            from scrapers.career_page_crawler import extract_domains_from_jobs, crawl_career_pages

            domains = extract_domains_from_jobs(all_jobs)
            if domains:
                _progress(f"Career Crawler: Found {len(domains)} unique company domains. Crawling...")
                loc_filters = [loc.lower() for loc in search_locations] if search_locations else []
                crawler_jobs = crawl_career_pages(
                    domains=domains,
                    search_terms=search_terms,
                    loc_filters=loc_filters,
                    max_domains=30,
                    progress_callback=_progress,
                )
                if crawler_jobs:
                    all_jobs.extend(crawler_jobs)
                    _progress(f"Career Crawler: Added {len(crawler_jobs)} hidden jobs")
                    from processing.deduplicator import deduplicate as _dedup2
                    all_jobs = _dedup2(all_jobs)
                    _progress(f"After re-dedup: {len(all_jobs)} unique jobs")
        except Exception as e:
            logger.warning("Career crawler failed: %s", e)
            _progress(f"Career Crawler error: {e}")

    # =========================================================================
    # 6. Auto-learn new companies from results
    # =========================================================================
    try:
        from scrapers.company_registry import learn_from_jobs
        learn_from_jobs(all_jobs)
        _progress(f"Auto-discovery: checked {len(all_jobs)} jobs for new company portals")
    except Exception as e:
        logger.warning("Company auto-discovery failed: %s", e)

    # =========================================================================
    # 7. Sort by date_posted descending
    # =========================================================================
    all_jobs.sort(key=lambda j: j.get("date_posted") or "0000-00-00", reverse=True)

    # =========================================================================
    # 8. Write output
    # =========================================================================
    _progress(f"Writing results to {output_format.upper()}...")
    if output_format == "csv":
        from output.csv_writer import write_csv
        filepath = write_csv(all_jobs)
    elif output_format == "json":
        from output.json_writer import write_json
        filepath = write_json(all_jobs)
    else:
        from output.excel_writer import write_excel
        filepath = write_excel(all_jobs)

    elapsed = time.time() - start_time
    _progress(f"\n✅ Done! {len(all_jobs)} jobs saved to {filepath} ({elapsed:.1f}s)")

    return all_jobs, filepath


# =============================================================================
# Safe wrappers for each scraper (catch all exceptions)
# =============================================================================

def _run_jobspy_safe(
    search_terms: list[str], location: str, sites: list[str],
    hours_old: int, results_per_site: int, country: str,
    job_type: str | None, is_remote: bool,
    progress_callback: Callable[[str], None],
) -> list[dict]:
    """Safely run the JobSpy scraper — per site, per search term."""
    all_results: list[dict] = []
    try:
        from jobspy import scrape_jobs
        from scrapers.jobspy_scraper import _map_jobspy_row

        for site in sites:
            for term in search_terms:
                try:
                    progress_callback(f"JobSpy: {site} - '{term}'...")
                    scrape_params = {
                        "site_name": [site],
                        "search_term": term,
                        "location": location,
                        "results_wanted": results_per_site,
                        "hours_old": hours_old,
                        "country_indeed": country,
                    }
                    if job_type and job_type.lower() != "any":
                        scrape_params["job_type"] = job_type
                    if is_remote:
                        scrape_params["is_remote"] = True

                    df = scrape_jobs(**scrape_params)
                    if df is not None and not df.empty:
                        for row in df.to_dict(orient="records"):
                            try:
                                job = _map_jobspy_row(row)
                                if job and job.get("job_url"):
                                    all_results.append(job)
                            except Exception as e:
                                logger.debug("Error mapping JobSpy row: %s", e)
                                continue
                        progress_callback(f"JobSpy: {site}/{term} → {len(df)} results")
                    else:
                        progress_callback(f"JobSpy: {site}/{term} → 0 results")
                except Exception as e:
                    logger.warning("JobSpy %s/%s failed: %s", site, term, e)
                    try:
                        progress_callback(f"JobSpy: {site}/{term} failed: {str(e)[:60]}")
                    except Exception as cb_err:
                        logger.debug("Progress callback failed: %s", cb_err)
                    continue

    except ImportError:
        logger.error("python-jobspy is not installed. Run: pip install python-jobspy")
        try:
            progress_callback("Error: python-jobspy not installed.")
        except Exception as cb_err:
            logger.debug("Progress callback failed: %s", cb_err)
    except Exception as e:
        logger.error("JobSpy safe wrapper failed: %s", e, exc_info=True)
        try:
            progress_callback(f"JobSpy error: {e}")
        except Exception as cb_err:
            logger.debug("Progress callback failed: %s", cb_err)

    return all_results


def _run_arbeitnow_safe(
    search_terms: list[str], location: str,
    search_locations: list[str] | None,
    language_filter: str | None,
    progress_callback: Callable[[str], None],
) -> list[dict]:
    """Safely run the Arbeitnow scraper."""
    try:
        from scrapers.apis.arbeitnow import scrape_arbeitnow
        return scrape_arbeitnow(
            search_terms=search_terms,
            location=location,
            search_locations=search_locations,
            language_filter=language_filter,
            progress_callback=progress_callback,
        )
    except Exception as e:
        logger.error("Arbeitnow safe wrapper failed: %s", e, exc_info=True)
        try:
            progress_callback(f"Arbeitnow error: {e}")
        except Exception as cb_err:
            logger.debug("Progress callback failed: %s", cb_err)
        return []


def _run_remotive_safe(
    search_terms: list[str], location: str,
    search_locations: list[str] | None,
    progress_callback: Callable[[str], None],
) -> list[dict]:
    """Safely run the Remotive scraper."""
    try:
        from scrapers.apis.remotive import scrape_remotive
        return scrape_remotive(
            search_terms=search_terms,
            location=location,
            search_locations=search_locations,
            progress_callback=progress_callback,
        )
    except Exception as e:
        logger.error("Remotive safe wrapper failed: %s", e, exc_info=True)
        try:
            progress_callback(f"Remotive error: {e}")
        except Exception as cb_err:
            logger.debug("Progress callback failed: %s", cb_err)
        return []


def _run_ats_discovery_safe(
    search_terms: list[str], location: str,
    search_locations: list[str] | None,
    hours_old: int,
    progress_callback: Callable[[str], None],
) -> list[dict]:
    """Safely run the ATS Discovery engine."""
    try:
        from scrapers.ats_discovery import discover_and_scrape
        return discover_and_scrape(
            search_terms=search_terms,
            location=location,
            search_locations=search_locations,
            hours_old=hours_old,
            progress_callback=progress_callback,
        )
    except Exception as e:
        logger.error("ATS Discovery safe wrapper failed: %s", e, exc_info=True)
        try:
            progress_callback(f"ATS Discovery error: {e}")
        except Exception as cb_err:
            logger.debug("Progress callback failed: %s", cb_err)
        return []


def _run_foundit_safe(
    search_terms: list[str], location: str,
    search_locations: list[str] | None,
    progress_callback: Callable[[str], None],
) -> list[dict]:
    """Safely run the Foundit.in scraper."""
    try:
        from scrapers.apis.foundit import scrape_foundit
        return scrape_foundit(
            search_terms=search_terms,
            location=location,
            search_locations=search_locations,
            progress_callback=progress_callback,
        )
    except Exception as e:
        logger.error("Foundit safe wrapper failed: %s", e, exc_info=True)
        try:
            progress_callback(f"Foundit error: {e}")
        except Exception as cb_err:
            logger.debug("Progress callback failed: %s", cb_err)
        return []


def _run_instahyre_safe(
    search_terms: list[str], location: str,
    search_locations: list[str] | None,
    progress_callback: Callable[[str], None],
) -> list[dict]:
    """Safely run the Instahyre scraper."""
    try:
        from scrapers.apis.instahyre import scrape_instahyre
        return scrape_instahyre(
            search_terms=search_terms,
            location=location,
            search_locations=search_locations,
            progress_callback=progress_callback,
        )
    except Exception as e:
        logger.error("Instahyre safe wrapper failed: %s", e, exc_info=True)
        try:
            progress_callback(f"Instahyre error: {e}")
        except Exception as cb_err:
            logger.debug("Progress callback failed: %s", cb_err)
        return []


def _run_serpapi_safe(
    search_terms: list[str], location: str,
    serpapi_key: str,
    progress_callback: Callable[[str], None],
    country: str = "",
    search_locations: list[str] | None = None,
) -> list[dict]:
    """Safely run SerpAPI dorking + URL routing."""
    try:
        from scrapers.serpapi_dorker import run_serpapi_dorks
        from scrapers.url_router import route_and_scrape

        # Use country name when location is empty (Country scope)
        serpapi_location = location
        if not serpapi_location and search_locations:
            serpapi_location = search_locations[0]  # e.g., "Germany"
        if not serpapi_location and country:
            serpapi_location = country

        urls = run_serpapi_dorks(
            search_terms=search_terms,
            location=serpapi_location,
            serpapi_key=serpapi_key,
            progress_callback=progress_callback,
        )

        if not urls:
            return []

        try:
            progress_callback(f"SerpAPI: Routing {len(urls)} discovered URLs to ATS scrapers...")
        except Exception as cb_err:
            logger.debug("Progress callback failed: %s", cb_err)

        jobs = route_and_scrape(
            urls=urls,
            search_terms=search_terms,
            location=serpapi_location,
            progress_callback=progress_callback,
        )

        return jobs

    except Exception as e:
        logger.error("SerpAPI safe wrapper failed: %s", e, exc_info=True)
        try:
            progress_callback(f"SerpAPI error: {e}")
        except Exception as cb_err:
            logger.debug("Progress callback failed: %s", cb_err)
        return []


# =============================================================================
# CLI interface
# =============================================================================

def main() -> None:
    """CLI entry point with argument parsing."""
    setup_logging()

    parser = argparse.ArgumentParser(
        description="Job Finder — Aggregate jobs from multiple sources.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--search", "-s", nargs="+",
                        default=DEFAULT_SEARCH_TERMS,
                        help="Job titles to search (multiple allowed)")
    parser.add_argument("--location", "-l", default=DEFAULT_LOCATION,
                        help=f"City or region (default: '{DEFAULT_LOCATION}')")
    parser.add_argument("--country", "-c", default=DEFAULT_COUNTRY,
                        help=f"Country (default: '{DEFAULT_COUNTRY}')")
    parser.add_argument("--scope", default="city",
                        choices=["city", "country", "europe"],
                        help="Location scope (city / country / europe)")
    parser.add_argument("--hours", type=int, default=DEFAULT_HOURS_OLD,
                        help=f"Max job age in hours (default: {DEFAULT_HOURS_OLD})")
    parser.add_argument("--results", type=int, default=DEFAULT_RESULTS_PER_SITE,
                        help=f"Results per site (default: {DEFAULT_RESULTS_PER_SITE})")
    parser.add_argument("--type", dest="job_type", default=None,
                        choices=["fulltime", "parttime", "contract", "internship"],
                        help="Filter by job type")
    parser.add_argument("--remote", action="store_true", help="Remote jobs only")
    parser.add_argument("--language", default=None,
                        choices=["English", "German", "French", "Spanish"],
                        help="Filter by job language")
    parser.add_argument("--no-jobspy", action="store_true", help="Disable JobSpy scraper")
    parser.add_argument("--no-ats", action="store_true", help="Disable ATS Discovery")
    parser.add_argument("--no-arbeitnow", action="store_true", help="Disable Arbeitnow API")
    parser.add_argument("--remotive", action="store_true", help="Enable Remotive API")
    parser.add_argument("--foundit", action="store_true", help="Enable Foundit.in (India)")
    parser.add_argument("--instahyre", action="store_true", help="Enable Instahyre (India)")
    parser.add_argument("--career-crawler", action="store_true", help="Enable career page crawler")
    parser.add_argument("--serpapi", action="store_true", help="Enable SerpAPI dorking")
    parser.add_argument("--format", dest="output_format", default="excel",
                        choices=["excel", "csv", "json"], help="Output format (default: excel)")
    parser.add_argument("--sites", nargs="+", default=None,
                        help="JobSpy sites to use (e.g., indeed linkedin google)")

    args = parser.parse_args()

    # Handle location scope
    if args.scope == "europe":
        search_locations = EUROPEAN_COUNTRIES
        location = ""
    elif args.scope == "country":
        search_locations = [args.country]
        location = ""
    else:
        search_locations = None  # Use location as-is
        location = args.location

    def cli_progress(msg: str) -> None:
        """Print progress to console."""
        print(f"  {msg}")

    jobs, filepath = run_search(
        search_terms=args.search,
        location=location,
        search_locations=search_locations,
        country=args.country,
        hours_old=args.hours,
        results_per_site=args.results,
        job_type=args.job_type,
        is_remote=args.remote,
        language_filter=args.language,
        enable_jobspy=not args.no_jobspy,
        jobspy_sites=args.sites,
        enable_ats_discovery=not args.no_ats,
        enable_arbeitnow=not args.no_arbeitnow,
        enable_remotive=args.remotive,
        enable_foundit=args.foundit,
        enable_instahyre=args.instahyre,
        enable_career_crawler=args.career_crawler,
        enable_serpapi=args.serpapi,
        output_format=args.output_format,
        progress_callback=cli_progress,
    )

    print(f"\n{'='*60}")
    print(f"  Results: {len(jobs)} jobs")
    print(f"  Output:  {os.path.abspath(filepath)}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
