"""
scrapers/google_dorker.py — Google dork query engine.

Uses the googlesearch-python library to execute Google dork queries,
discover job posting URLs from company career pages and ATS platforms.
"""

import logging
import random
import time
from typing import Callable

from config import (
    DORK_TEMPLATES,
    ENGLISH_EXTRA_DORKS,
    GERMAN_EXTRA_DORKS,
    GOOGLE_DORK_DELAY_MIN,
    GOOGLE_DORK_DELAY_MAX,
    GOOGLE_DORK_RESULTS_PER_QUERY,
)

logger = logging.getLogger(__name__)


def run_dork_queries(
    search_term: str,
    location: str,
    hours_old: int = 168,
    language_filter: str | None = None,
    dork_templates: list[str] | None = None,
    results_per_query: int = GOOGLE_DORK_RESULTS_PER_QUERY,
    delay_range: tuple[float, float] = (GOOGLE_DORK_DELAY_MIN, GOOGLE_DORK_DELAY_MAX),
    progress_callback: Callable[[str], None] | None = None,
) -> list[str]:
    """
    Execute Google dork queries to discover job posting URLs.

    Takes dork templates, fills in {keyword} and {location}, runs each query
    via googlesearch-python, and collects all resulting URLs.

    Args:
        search_term: Job title or keywords to insert into dork templates.
        location: City or region to insert into dork templates.
        hours_old: Max age (used to select time filter for Google).
        language_filter: "English", "German", or None. Appends extra dork templates.
        dork_templates: List of dork query templates. Defaults to config.DORK_TEMPLATES.
        results_per_query: Max number of results per dork query.
        delay_range: (min_seconds, max_seconds) to wait between queries.
        progress_callback: Optional function for progress updates.

    Returns:
        Deduplicated list of discovered URLs.
    """
    if dork_templates is None:
        dork_templates = list(DORK_TEMPLATES)

    # Append language-specific templates
    if language_filter == "English":
        dork_templates = dork_templates + ENGLISH_EXTRA_DORKS
    elif language_filter == "German":
        dork_templates = dork_templates + GERMAN_EXTRA_DORKS

    # Build actual queries from templates
    queries = []
    for template in dork_templates:
        query = template.replace("{keyword}", search_term).replace("{location}", location)
        queries.append(query)

    total_queries = len(queries)
    logger.info("Google Dorking: %d queries to execute.", total_queries)

    if progress_callback:
        progress_callback(f"Google Dorking: Running {total_queries} dork queries...")

    all_urls: list[str] = []
    failed_queries = 0

    try:
        from googlesearch import search as google_search
    except ImportError:
        logger.error("googlesearch-python not installed. Run: pip install googlesearch-python")
        if progress_callback:
            progress_callback("Error: googlesearch-python not installed.")
        return []

    for i, query in enumerate(queries, 1):
        if progress_callback:
            progress_callback(f"Running dork {i}/{total_queries}: {query[:80]}...")

        logger.info("Dork %d/%d: %s", i, total_queries, query)

        try:
            results = list(google_search(
                query,
                num_results=results_per_query,
                lang="en",
                sleep_interval=0,  # We handle our own delays
            ))

            if results:
                logger.info("  → %d URLs found.", len(results))
                all_urls.extend(results)
            else:
                logger.info("  → No results.")

        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "too many" in error_str or "rate" in error_str:
                logger.warning("Rate limited on dork %d. Waiting 30 seconds...", i)
                if progress_callback:
                    progress_callback(f"⚠️ Rate limited on dork {i}. Waiting 30s...")
                time.sleep(30)
                failed_queries += 1
            else:
                logger.warning("Dork %d failed: %s", i, e)
                failed_queries += 1

        # Random delay between queries
        if i < total_queries:
            delay = random.uniform(delay_range[0], delay_range[1])
            logger.debug("Sleeping %.1f seconds between dork queries...", delay)
            time.sleep(delay)

    # Deduplicate URLs
    seen: set[str] = set()
    unique_urls: list[str] = []
    for url in all_urls:
        url_clean = url.strip().rstrip("/")
        if url_clean and url_clean not in seen:
            seen.add(url_clean)
            unique_urls.append(url_clean)

    logger.info(
        "Google Dorking: %d total URLs found, %d unique, %d queries failed.",
        len(all_urls), len(unique_urls), failed_queries,
    )

    if progress_callback:
        progress_callback(
            f"Google Dorking: {len(unique_urls)} unique URLs from {total_queries} queries "
            f"({failed_queries} failed)."
        )

    return unique_urls
