"""
scrapers/company_list_updater.py — Download company lists from GitHub.

Fetches curated lists of companies from open-source repos that track
which companies use which ATS platforms. Merges them into our registry.

Run periodically (e.g., weekly) to discover new companies.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Callable

import requests

from scrapers.company_registry import load_registry, save_registry

logger = logging.getLogger(__name__)

CACHE_FILE = "company_lists_cache.json"
CACHE_MAX_AGE_DAYS = 7

# Known GitHub sources for company lists
# These repos maintain lists of companies and their ATS career page URLs
GITHUB_SOURCES = [
    {
        "name": "Greenhouse companies",
        "url": "https://raw.githubusercontent.com/Feashliaa/job-board-aggregator/main/greenhouse_companies.json",
        "ats": "greenhouse",
        "parser": "json_list",
    },
    {
        "name": "Lever companies",
        "url": "https://raw.githubusercontent.com/Feashliaa/job-board-aggregator/main/lever_companies.json",
        "ats": "lever",
        "parser": "json_list",
    },
    {
        "name": "Ashby companies",
        "url": "https://raw.githubusercontent.com/Feashliaa/job-board-aggregator/main/ashby_companies.json",
        "ats": "ashby",
        "parser": "json_list",
    },
]

# Alternative sources — try each, use whichever works
GITHUB_SOURCES_ALTERNATIVES = [
    {
        "name": "Greenhouse companies (alt 1)",
        "url": "https://raw.githubusercontent.com/nickcis/companies-on-greenhouse/main/companies.json",
        "ats": "greenhouse",
        "parser": "json_list",
    },
    {
        "name": "Greenhouse companies (alt 2)",
        "url": "https://raw.githubusercontent.com/Joshuah143/JOB_BOARD_SCRAPER/main/greenhouse_companies.json",
        "ats": "greenhouse",
        "parser": "json_list",
    },
]


def should_update() -> bool:
    """Check if we need to refresh the company lists."""
    if not os.path.exists(CACHE_FILE):
        return True
    try:
        with open(CACHE_FILE, "r") as f:
            cache = json.load(f)
        last_updated = datetime.fromisoformat(cache.get("updated", "2000-01-01"))
        return datetime.now() - last_updated > timedelta(days=CACHE_MAX_AGE_DAYS)
    except Exception:
        return True


def _fetch_and_parse_source(source: dict, registry: dict) -> int:
    """Fetch a single source and add slugs to registry. Returns count of new companies."""
    resp = requests.get(source["url"], timeout=30)
    if resp.status_code != 200:
        logger.warning("Failed to fetch %s: HTTP %d", source["name"], resp.status_code)
        return 0

    data = resp.json()
    ats = source["ats"]

    # Parse based on format
    slugs = []
    if source["parser"] == "json_list":
        if isinstance(data, list):
            for item in data:
                if isinstance(item, str):
                    slugs.append(item)
                elif isinstance(item, dict):
                    slug = item.get("slug") or item.get("company_slug") or item.get("id") or item.get("name", "")
                    if slug:
                        slugs.append(str(slug).lower().strip())

    # Add to registry
    new_count = 0
    for slug in slugs:
        if not slug or len(slug) < 2:
            continue
        key = f"{ats}:{slug}"
        if key not in registry["companies"]:
            registry["companies"][key] = {
                "ats": ats,
                "slug": slug,
                "company_name": slug.replace("-", " ").title(),
                "discovered_from": "github_list",
                "discovered_date": datetime.now().isoformat(),
            }
            new_count += 1

    logger.info("%s: %d slugs found, %d new", source["name"], len(slugs), new_count)
    return new_count


def update_company_lists(
    force: bool = False,
    progress_callback: Callable[[str], None] | None = None,
) -> int:
    """
    Download company lists from GitHub and merge into registry.

    Args:
        force: If True, update even if cache is fresh
        progress_callback: Optional progress updates

    Returns:
        Number of new companies added
    """
    if not force and not should_update():
        logger.info("Company lists cache is fresh. Skipping update.")
        if progress_callback:
            progress_callback("Company lists: cache is fresh, skipping download.")
        return 0

    if progress_callback:
        progress_callback("Downloading company lists from GitHub...")

    registry = load_registry()
    total_new = 0

    for source in GITHUB_SOURCES:
        try:
            if progress_callback:
                progress_callback(f"Fetching {source['name']}...")

            new_count = _fetch_and_parse_source(source, registry)
            total_new += new_count

            if progress_callback:
                progress_callback(f"{source['name']}: {new_count} new companies")

        except Exception as e:
            logger.warning("Error fetching %s: %s", source["name"], e)
            if progress_callback:
                progress_callback(f"Error fetching {source['name']}: {str(e)[:60]}")

    # Try alternative sources for additional coverage
    for source in GITHUB_SOURCES_ALTERNATIVES:
        try:
            new_count = _fetch_and_parse_source(source, registry)
            total_new += new_count
            if new_count > 0:
                logger.info("%s: %d new companies", source["name"], new_count)
        except Exception as e:
            logger.debug("Alternative source %s failed: %s", source["name"], e)

    if total_new > 0:
        save_registry(registry)

    # Update cache timestamp
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump({"updated": datetime.now().isoformat(), "total_new": total_new}, f)
    except Exception:
        pass

    logger.info("Company list update: %d new companies added. Registry total: %d",
                total_new, len(registry["companies"]))
    if progress_callback:
        progress_callback(f"Company lists updated: {total_new} new companies. "
                         f"Total in registry: {len(registry['companies'])}")

    return total_new
