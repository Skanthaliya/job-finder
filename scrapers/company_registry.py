"""
scrapers/company_registry.py — Auto-growing company registry.

Tracks discovered companies and their ATS platforms.
When we find a job from a new company (via Indeed, LinkedIn, etc.),
we check if their career page uses a known ATS and save the slug.
Next run, we query that company's ATS directly.
"""

import json
import logging
import os
import re
from datetime import datetime

logger = logging.getLogger(__name__)

REGISTRY_FILE = "company_registry.json"


def load_registry() -> dict:
    """Load the company registry from disk."""
    if os.path.exists(REGISTRY_FILE):
        try:
            with open(REGISTRY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"companies": {}, "updated": None}


def save_registry(registry: dict):
    """Save the company registry to disk."""
    registry["updated"] = datetime.now().isoformat()
    try:
        with open(REGISTRY_FILE, "w") as f:
            json.dump(registry, f, indent=2)
    except Exception as e:
        logger.error("Failed to save registry: %s", e)


def extract_ats_from_url(url: str) -> tuple[str, str] | None:
    """
    Check if a URL belongs to a known ATS platform.
    Returns (ats_name, company_slug) or None.
    """
    patterns = {
        "greenhouse": r"boards\.greenhouse\.io/([\w-]+)",
        "lever": r"jobs\.lever\.co/([\w-]+)",
        "ashby": r"jobs\.ashbyhq\.com/([\w-]+)",
        "smartrecruiters": r"jobs\.smartrecruiters\.com/([\w-]+)",
        "personio": r"([\w-]+)\.jobs\.personio\.de",
        "workday": r"([\w-]+)\.wd\d+\.myworkdayjobs\.com",
    }
    for ats, pattern in patterns.items():
        match = re.search(pattern, url)
        if match:
            return ats, match.group(1)
    return None


def learn_from_jobs(jobs: list[dict]):
    """
    Analyze job results and discover new company ATS slugs.
    Adds newly discovered companies to the registry.
    """
    registry = load_registry()
    new_count = 0

    for job in jobs:
        url = job.get("job_url") or ""
        company_url = job.get("company_url") or ""

        for check_url in [url, company_url]:
            result = extract_ats_from_url(check_url)
            if result:
                ats, slug = result
                key = f"{ats}:{slug}"
                if key not in registry["companies"]:
                    entry = {
                        "ats": ats,
                        "slug": slug,
                        "company_name": job.get("company", slug),
                        "discovered_from": job.get("source", "unknown"),
                        "discovered_date": datetime.now().isoformat(),
                    }
                    # For Workday, save full URL (slug alone isn't enough)
                    if ats == "workday":
                        entry["url"] = check_url
                    registry["companies"][key] = entry
                    new_count += 1
                    logger.info("New company discovered: %s on %s", slug, ats)

    if new_count > 0:
        save_registry(registry)
        logger.info(
            "Registry updated: %d new companies added (total: %d)",
            new_count,
            len(registry["companies"]),
        )


def get_discovered_slugs(ats: str) -> list[str]:
    """Get all discovered company slugs for a specific ATS platform."""
    registry = load_registry()
    return [v["slug"] for v in registry["companies"].values() if v["ats"] == ats]
