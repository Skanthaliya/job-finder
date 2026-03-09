"""
main.py — CLI entry point and main orchestrator for Job Finder.

Runs all enabled scrapers in parallel, merges results, deduplicates, detects
languages, and outputs to Excel or CSV.

Usage:
    python main.py
    python main.py --search "Data Engineer" --location "Munich" --remote
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
    DEFAULT_LOCATION,
    DEFAULT_COUNTRY,
    DEFAULT_HOURS_OLD,
    DEFAULT_RESULTS_PER_SITE,
    JOBSPY_SITES,
    LOG_FILE,
    LOG_LEVEL,
)

# Configure logging
def setup_logging() -> None:
    """Set up logging to both console and file."""
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    log_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)

    # Root logger
    root_logger = logging.getLogger()
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
    search_term: str = DEFAULT_SEARCH_TERM,
    location: str = DEFAULT_LOCATION,
    country: str = DEFAULT_COUNTRY,
    hours_old: int = DEFAULT_HOURS_OLD,
    results_per_site: int = DEFAULT_RESULTS_PER_SITE,
    job_type: str | None = None,
    is_remote: bool = False,
    language_filter: str | None = None,
    enable_jobspy: bool = True,
    jobspy_sites: list[str] | None = None,
    enable_google_dorking: bool = True,
    enable_arbeitnow: bool = True,
    enable_remotive: bool = False,
    output_format: str = "excel",
    custom_dorks: list[str] | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> tuple[list[dict], str]:
    """
    Main orchestrator. Runs all enabled scrapers, merges, deduplicates, filters, and outputs.

    Args:
        search_term: Job title or keywords.
        location: City or region.
        country: Country name.
        hours_old: Max age of job postings in hours.
        results_per_site: Max results per job board site.
        job_type: Filter by type ("fulltime", "parttime", "contract", "internship").
        is_remote: Only remote jobs.
        language_filter: "English", "German", or None for all.
        enable_jobspy: Enable python-jobspy scraper.
        jobspy_sites: List of sites for JobSpy.
        enable_google_dorking: Enable Google dork search.
        enable_arbeitnow: Enable Arbeitnow API.
        enable_remotive: Enable Remotive API.
        output_format: "excel" or "csv".
        custom_dorks: Custom dork queries to append.
        progress_callback: Function to call with progress updates.

    Returns:
        Tuple of (list of job dicts, output filepath).
    """
    start_time = time.time()

    def _progress(msg: str) -> None:
        """Send progress update to callback and logger."""
        logger.info(msg)
        if progress_callback:
            progress_callback(msg)

    _progress(f"🔍 Starting job search: '{search_term}' in '{location}', {country}")
    _progress(f"   Filters: hours_old={hours_old}, job_type={job_type}, remote={is_remote}, language={language_filter}")

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
                search_term, location, sites, hours_old, results_per_site,
                country, job_type, is_remote, _progress,
            )

        # --- Arbeitnow ---
        if enable_arbeitnow:
            _progress("Launching Arbeitnow API scraper...")
            futures["arbeitnow"] = executor.submit(
                _run_arbeitnow_safe,
                search_term, location, language_filter, _progress,
            )

        # --- Remotive ---
        if enable_remotive:
            _progress("Launching Remotive API scraper...")
            futures["remotive"] = executor.submit(
                _run_remotive_safe,
                search_term, location, _progress,
            )

        # --- Google Dorking ---
        if enable_google_dorking:
            _progress("Launching Google Dorking engine...")
            futures["google_dork"] = executor.submit(
                _run_google_dorking_safe,
                search_term, location, hours_old, language_filter,
                custom_dorks, _progress,
            )

        # Collect results
        for name, future in futures.items():
            try:
                result = future.result(timeout=300)  # 5-minute timeout per scraper
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
        # Still create an empty output file
        if output_format == "csv":
            from output.csv_writer import write_csv
            filepath = write_csv([])
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
    # 3. Detect languages
    # =========================================================================
    _progress("Detecting job languages...")
    from processing.language_detector import detect_languages_batch
    all_jobs = detect_languages_batch(all_jobs)

    # =========================================================================
    # 4. Apply language filter
    # =========================================================================
    if language_filter and language_filter != "All":
        pre_filter_count = len(all_jobs)
        all_jobs = [
            j for j in all_jobs
            if j.get("language") == language_filter or j.get("language") == "unknown"
        ]
        filtered_count = pre_filter_count - len(all_jobs)
        _progress(f"Language filter '{language_filter}': kept {len(all_jobs)}, removed {filtered_count}")

    # =========================================================================
    # 5. Deduplicate
    # =========================================================================
    _progress("Deduplicating results...")
    from processing.deduplicator import deduplicate
    all_jobs = deduplicate(all_jobs)
    _progress(f"After deduplication: {len(all_jobs)} unique jobs")

    # =========================================================================
    # 6. Sort by date_posted descending
    # =========================================================================
    all_jobs.sort(key=lambda j: j.get("date_posted") or "0000-00-00", reverse=True)

    # =========================================================================
    # 7. Write output
    # =========================================================================
    _progress(f"Writing results to {output_format.upper()}...")
    if output_format == "csv":
        from output.csv_writer import write_csv
        filepath = write_csv(all_jobs)
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
    search_term: str, location: str, sites: list[str],
    hours_old: int, results_per_site: int, country: str,
    job_type: str | None, is_remote: bool,
    progress_callback: Callable[[str], None],
) -> list[dict]:
    """Safely run the JobSpy scraper."""
    try:
        from scrapers.jobspy_scraper import scrape_jobspy
        return scrape_jobspy(
            search_term=search_term,
            location=location,
            sites=sites,
            hours_old=hours_old,
            results_wanted=results_per_site,
            country_indeed=country,
            job_type=job_type,
            is_remote=is_remote,
            progress_callback=progress_callback,
        )
    except Exception as e:
        logger.error("JobSpy safe wrapper failed: %s", e, exc_info=True)
        if progress_callback:
            progress_callback(f"JobSpy error: {e}")
        return []


def _run_arbeitnow_safe(
    search_term: str, location: str, language_filter: str | None,
    progress_callback: Callable[[str], None],
) -> list[dict]:
    """Safely run the Arbeitnow scraper."""
    try:
        from scrapers.apis.arbeitnow import scrape_arbeitnow
        return scrape_arbeitnow(
            search_term=search_term,
            location=location,
            language_filter=language_filter,
            progress_callback=progress_callback,
        )
    except Exception as e:
        logger.error("Arbeitnow safe wrapper failed: %s", e, exc_info=True)
        if progress_callback:
            progress_callback(f"Arbeitnow error: {e}")
        return []


def _run_remotive_safe(
    search_term: str, location: str,
    progress_callback: Callable[[str], None],
) -> list[dict]:
    """Safely run the Remotive scraper."""
    try:
        from scrapers.apis.remotive import scrape_remotive
        return scrape_remotive(
            search_term=search_term,
            location=location,
            progress_callback=progress_callback,
        )
    except Exception as e:
        logger.error("Remotive safe wrapper failed: %s", e, exc_info=True)
        if progress_callback:
            progress_callback(f"Remotive error: {e}")
        return []


def _run_google_dorking_safe(
    search_term: str, location: str, hours_old: int,
    language_filter: str | None, custom_dorks: list[str] | None,
    progress_callback: Callable[[str], None],
) -> list[dict]:
    """Safely run the Google Dorking pipeline (dork → URL router → ATS scrapers)."""
    try:
        from scrapers.google_dorker import run_dork_queries
        from scrapers.url_router import route_and_scrape
        from config import (
            DORK_TEMPLATES,
            GOOGLE_DORK_RESULTS_PER_QUERY,
            GOOGLE_DORK_DELAY_MIN,
            GOOGLE_DORK_DELAY_MAX,
        )

        # Build dork template list
        templates = list(DORK_TEMPLATES)
        if custom_dorks:
            templates.extend(custom_dorks)

        # Run dork queries
        urls = run_dork_queries(
            search_term=search_term,
            location=location,
            hours_old=hours_old,
            language_filter=language_filter,
            dork_templates=templates,
            results_per_query=GOOGLE_DORK_RESULTS_PER_QUERY,
            delay_range=(GOOGLE_DORK_DELAY_MIN, GOOGLE_DORK_DELAY_MAX),
            progress_callback=progress_callback,
        )

        if not urls:
            if progress_callback:
                progress_callback("Google Dorking: No URLs discovered.")
            return []

        if progress_callback:
            progress_callback(f"Google Dorking: {len(urls)} URLs discovered. Scraping ATS pages...")

        # Route URLs to ATS scrapers
        jobs = route_and_scrape(
            urls=urls,
            search_term=search_term,
            location=location,
            progress_callback=progress_callback,
        )

        return jobs

    except Exception as e:
        logger.error("Google Dorking safe wrapper failed: %s", e, exc_info=True)
        if progress_callback:
            progress_callback(f"Google Dorking error: {e}")
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
    parser.add_argument("--search", "-s", default=DEFAULT_SEARCH_TERM,
                        help=f"Job title or keywords (default: '{DEFAULT_SEARCH_TERM}')")
    parser.add_argument("--location", "-l", default=DEFAULT_LOCATION,
                        help=f"City or region (default: '{DEFAULT_LOCATION}')")
    parser.add_argument("--country", "-c", default=DEFAULT_COUNTRY,
                        help=f"Country (default: '{DEFAULT_COUNTRY}')")
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
    parser.add_argument("--no-dork", action="store_true", help="Disable Google dorking")
    parser.add_argument("--no-arbeitnow", action="store_true", help="Disable Arbeitnow API")
    parser.add_argument("--remotive", action="store_true", help="Enable Remotive API")
    parser.add_argument("--format", dest="output_format", default="excel",
                        choices=["excel", "csv"], help="Output format (default: excel)")
    parser.add_argument("--sites", nargs="+", default=None,
                        help="JobSpy sites to use (e.g., indeed linkedin google)")

    args = parser.parse_args()

    def cli_progress(msg: str) -> None:
        """Print progress to console."""
        print(f"  {msg}")

    jobs, filepath = run_search(
        search_term=args.search,
        location=args.location,
        country=args.country,
        hours_old=args.hours,
        results_per_site=args.results,
        job_type=args.job_type,
        is_remote=args.remote,
        language_filter=args.language,
        enable_jobspy=not args.no_jobspy,
        jobspy_sites=args.sites,
        enable_google_dorking=not args.no_dork,
        enable_arbeitnow=not args.no_arbeitnow,
        enable_remotive=args.remotive,
        output_format=args.output_format,
        progress_callback=cli_progress,
    )

    print(f"\n{'='*60}")
    print(f"  Results: {len(jobs)} jobs")
    print(f"  Output:  {os.path.abspath(filepath)}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
