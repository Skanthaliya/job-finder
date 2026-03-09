"""
output/csv_writer.py — CSV fallback output writer.

Writes all job data to a CSV file with proper quoting and UTF-8 encoding.
"""

import csv
import logging
import os
from datetime import datetime

from config import OUTPUT_DIR
from processing.normalizer import UNIFIED_SCHEMA_FIELDS

logger = logging.getLogger(__name__)


def write_csv(jobs: list[dict], filename: str | None = None) -> str:
    """
    Write job results to a CSV file.

    Args:
        jobs: List of job dicts (unified schema).
        filename: Optional filename. Defaults to jobs_YYYYMMDD_HHMMSS.csv.

    Returns:
        The filepath of the created CSV file.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"jobs_{timestamp}.csv"

    filepath = os.path.join(OUTPUT_DIR, filename)

    logger.info("Writing %d jobs to CSV: %s", len(jobs), filepath)

    # Sort by date_posted descending
    sorted_jobs = sorted(
        jobs,
        key=lambda j: j.get("date_posted") or "0000-00-00",
        reverse=True,
    )

    try:
        with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=UNIFIED_SCHEMA_FIELDS,
                quoting=csv.QUOTE_ALL,
                extrasaction="ignore",
            )
            writer.writeheader()

            for job in sorted_jobs:
                # Ensure all fields exist
                row = {field: job.get(field) for field in UNIFIED_SCHEMA_FIELDS}
                writer.writerow(row)

        logger.info("CSV file saved: %s (%d jobs)", filepath, len(sorted_jobs))
    except Exception as e:
        logger.error("Error writing CSV file: %s", e, exc_info=True)
        raise

    return filepath
