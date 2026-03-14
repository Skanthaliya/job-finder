"""
filtering/language_filter.py — Filter jobs by detected language requirement.
"""

import logging
from typing import Callable

logger = logging.getLogger(__name__)


def filter_by_language(
    jobs: list[dict],
    language_filter: str | None,
    progress_callback: Callable[[str], None] | None = None,
) -> list[dict]:
    """Filter jobs by language requirement. Returns all jobs if filter is None or 'All'."""
    if not language_filter or language_filter == "All":
        return jobs

    pre_count = len(jobs)
    filtered = []

    for j in jobs:
        lang = j.get("language", "unknown")

        if language_filter == "English":
            if lang in ("English", "English (German plus)"):
                filtered.append(j)
            elif lang == "unknown":
                desc = j.get("description") or ""
                if len(desc.strip()) < 50:
                    filtered.append(j)

        elif language_filter == "English (German plus)":
            if lang == "English (German plus)":
                filtered.append(j)

        elif language_filter == "German":
            if lang in ("German", "English (German plus)"):
                filtered.append(j)

        else:
            if lang == language_filter or lang == "unknown":
                filtered.append(j)

    removed = pre_count - len(filtered)
    if progress_callback:
        progress_callback(
            f"Language filter '{language_filter}': kept {len(filtered)}, removed {removed}"
        )

    return filtered
