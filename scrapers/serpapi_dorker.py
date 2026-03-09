"""
scrapers/serpapi_dorker.py — SerpAPI-based Google dorking.

Uses SerpAPI (free tier: 100 searches/month) to run Google dork queries
without getting rate-limited. Batches multiple roles into single queries
to conserve the monthly quota.

Sign up at https://serpapi.com for a free API key.
"""

import json
import logging
import os
from datetime import datetime
from typing import Callable

import requests

logger = logging.getLogger(__name__)

SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")
QUOTA_FILE = "serpapi_usage.json"  # Track monthly usage

# Smart dork templates that combine multiple roles with OR
# {roles_or} gets replaced with: "Product Owner" OR "Scrum Master" OR "Project Manager"
SMART_DORK_TEMPLATES = [
    'site:myworkdayjobs.com ({roles_or}) "{location}"',
    'site:boards.greenhouse.io ({roles_or}) "{location}"',
    'site:jobs.lever.co ({roles_or}) "{location}"',
    'site:jobs.ashbyhq.com ({roles_or}) "{location}"',
    'site:jobs.personio.de ({roles_or}) "{location}"',
    'site:jobs.smartrecruiters.com ({roles_or}) "{location}"',
    'inurl:careers ({roles_or}) "{location}" -site:linkedin.com -site:indeed.com',
    '({roles_or}) "{location}" "hiring" inurl:jobs -site:linkedin.com -site:indeed.com -site:glassdoor.com',
]


def get_monthly_usage() -> int:
    """Get number of SerpAPI searches used this month."""
    try:
        if os.path.exists(QUOTA_FILE):
            with open(QUOTA_FILE, "r") as f:
                data = json.load(f)
            # Reset if different month
            if data.get("month") != datetime.now().strftime("%Y-%m"):
                return 0
            return data.get("count", 0)
    except Exception:
        pass
    return 0


def increment_usage(count: int = 1):
    """Increment monthly usage counter."""
    try:
        current = get_monthly_usage()
        with open(QUOTA_FILE, "w") as f:
            json.dump(
                {
                    "month": datetime.now().strftime("%Y-%m"),
                    "count": current + count,
                    "last_used": datetime.now().isoformat(),
                },
                f,
            )
    except Exception:
        pass


def run_serpapi_dorks(
    search_terms: list[str],
    location: str,
    max_queries: int = 15,
    serpapi_key: str = "",
    progress_callback: Callable[[str], None] | None = None,
) -> list[str]:
    """
    Run Google dork queries via SerpAPI.

    Combines multiple search terms into OR queries to conserve quota.
    E.g., 4 roles x 8 templates = 8 queries (not 32).

    Returns: list of discovered URLs
    """
    api_key = serpapi_key or SERPAPI_KEY
    if not api_key:
        logger.info("No SERPAPI_KEY set. Skipping SerpAPI dorking.")
        if progress_callback:
            progress_callback("SerpAPI: No API key configured. Skipping.")
        return []

    # Check quota
    used = get_monthly_usage()
    remaining = 100 - used
    if remaining <= 0:
        logger.info("SerpAPI monthly quota exhausted (%d/100 used).", used)
        if progress_callback:
            progress_callback(f"SerpAPI: Monthly quota exhausted ({used}/100 used).")
        return []

    # Limit queries to remaining quota
    actual_max = min(max_queries, remaining, len(SMART_DORK_TEMPLATES))

    if progress_callback:
        progress_callback(
            f"SerpAPI: {remaining} queries remaining this month. Running {actual_max} dorks..."
        )

    # Build the OR clause: "Product Owner" OR "Scrum Master" OR "Project Manager"
    roles_or = " OR ".join(f'"{term}"' for term in search_terms)

    # Build queries from templates
    queries = []
    for template in SMART_DORK_TEMPLATES[:actual_max]:
        query = template.replace("{roles_or}", roles_or).replace("{location}", location)
        queries.append(query)

    all_urls = []
    queries_used = 0

    for i, query in enumerate(queries, 1):
        if progress_callback:
            progress_callback(f"SerpAPI dork {i}/{len(queries)}: {query[:80]}...")

        try:
            params = {
                "engine": "google",
                "q": query,
                "api_key": api_key,
                "num": 20,
            }

            resp = requests.get(
                "https://serpapi.com/search", params=params, timeout=30
            )
            resp.raise_for_status()
            data = resp.json()

            # Extract URLs from organic results
            organic = data.get("organic_results", [])
            for result in organic:
                url = result.get("link")
                if url:
                    all_urls.append(url)

            queries_used += 1
            logger.info("SerpAPI dork %d: %d results", i, len(organic))

        except Exception as e:
            logger.warning("SerpAPI dork %d failed: %s", i, e)
            if progress_callback:
                progress_callback(f"SerpAPI dork {i} failed: {str(e)[:60]}")

    # Track usage
    increment_usage(queries_used)

    # Deduplicate
    unique_urls = list(
        dict.fromkeys(url.strip().rstrip("/") for url in all_urls if url)
    )

    if progress_callback:
        progress_callback(
            f"SerpAPI: {len(unique_urls)} unique URLs from {queries_used} queries. "
            f"Monthly usage: {used + queries_used}/100"
        )

    return unique_urls
