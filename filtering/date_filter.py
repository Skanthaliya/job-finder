"""
filtering/date_filter.py — Filter jobs by posting date.
"""

import logging
from datetime import datetime, timedelta
from typing import Callable

from config import HOURS_IN_YEAR

logger = logging.getLogger(__name__)


def filter_by_date(
    jobs: list[dict],
    hours_old: int,
    progress_callback: Callable[[str], None] | None = None,
) -> list[dict]:
    """Remove jobs older than hours_old. Jobs without a date are kept."""
    if not hours_old or hours_old >= HOURS_IN_YEAR:
        return jobs

    cutoff_date = (datetime.now() - timedelta(hours=hours_old)).strftime("%Y-%m-%d")
    pre_count = len(jobs)

    filtered = [
        j for j in jobs
        if not j.get("date_posted") or j["date_posted"] >= cutoff_date
    ]

    removed = pre_count - len(filtered)
    if removed > 0 and progress_callback:
        progress_callback(
            f"Date filter: removed {removed} jobs older than {hours_old}h (before {cutoff_date})"
        )

    return filtered
