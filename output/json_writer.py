"""
output/json_writer.py — JSON output writer.

Writes all job data to a JSON file for programmatic consumption.
"""

import json
import logging
import os
from datetime import datetime

from config import OUTPUT_DIR
from processing.normalizer import UNIFIED_SCHEMA_FIELDS

logger = logging.getLogger(__name__)


def write_json(jobs: list[dict], filename: str | None = None) -> str:
    """Write job results to a JSON file.

    Args:
        jobs: List of job dicts (unified schema).
        filename: Optional filename. Defaults to jobs_YYYYMMDD_HHMMSS.json.

    Returns:
        The filepath of the created JSON file.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"jobs_{timestamp}.json"

    filepath = os.path.join(OUTPUT_DIR, filename)

    logger.info("Writing %d jobs to JSON: %s", len(jobs), filepath)

    sorted_jobs = sorted(
        jobs,
        key=lambda j: j.get("date_posted") or "0000-00-00",
        reverse=True,
    )

    clean_jobs = []
    for job in sorted_jobs:
        row = {field: job.get(field) for field in UNIFIED_SCHEMA_FIELDS}
        for extra in ("skills", "salary_estimated_min", "salary_estimated_max", "salary_estimated_currency"):
            if extra in job:
                row[extra] = job[extra]
        clean_jobs.append(row)

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(clean_jobs, f, ensure_ascii=False, indent=2, default=str)

        logger.info("JSON file saved: %s (%d jobs)", filepath, len(clean_jobs))
    except Exception as e:
        logger.error("Error writing JSON file: %s", e, exc_info=True)
        raise

    return filepath
