"""
processing/language_detector.py — Detect language of job descriptions.

Uses the langdetect library to classify description text as English, German, etc.
"""

import logging

logger = logging.getLogger(__name__)

# Map ISO 639-1 codes to human-readable language names
LANGUAGE_MAP = {
    "en": "English",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "pl": "Polish",
    "cs": "Czech",
    "da": "Danish",
    "sv": "Swedish",
    "no": "Norwegian",
    "fi": "Finnish",
    "ru": "Russian",
    "ja": "Japanese",
    "zh-cn": "Chinese",
    "zh-tw": "Chinese",
    "ko": "Korean",
    "ar": "Arabic",
    "hi": "Hindi",
    "tr": "Turkish",
    "hu": "Hungarian",
    "ro": "Romanian",
    "el": "Greek",
    "uk": "Ukrainian",
    "bg": "Bulgarian",
    "hr": "Croatian",
    "sk": "Slovak",
    "sl": "Slovenian",
    "et": "Estonian",
    "lv": "Latvian",
    "lt": "Lithuanian",
}


def detect_language(text: str | None) -> str:
    """
    Detect the language of a given text string.

    Args:
        text: The text to analyze (typically a job description).

    Returns:
        Human-readable language name (e.g. "English", "German") or "unknown".
    """
    if not text or len(text.strip()) < 30:
        return "unknown"

    try:
        from langdetect import detect

        # Use a clean subset of text for more reliable detection
        # Strip HTML tags if present
        import re
        clean_text = re.sub(r"<[^>]+>", " ", text)
        clean_text = re.sub(r"\s+", " ", clean_text).strip()

        if len(clean_text) < 30:
            return "unknown"

        iso_code = detect(clean_text)
        return LANGUAGE_MAP.get(iso_code, iso_code)

    except ImportError:
        logger.warning("langdetect library not installed. Run: pip install langdetect")
        return "unknown"
    except Exception as e:
        logger.debug("Language detection failed: %s", e)
        return "unknown"


def detect_languages_batch(jobs: list[dict]) -> list[dict]:
    """
    Detect languages for a batch of job dicts.

    For each job, detects the language from the 'description' field
    and sets the 'language' field.

    Args:
        jobs: List of job dicts (unified schema).

    Returns:
        The same list with 'language' field populated.
    """
    logger.info("Detecting languages for %d jobs...", len(jobs))

    # Set seed for reproducibility of langdetect
    try:
        from langdetect import DetectorFactory
        DetectorFactory.seed = 0
    except ImportError:
        logger.warning("langdetect not installed; all languages will be 'unknown'.")

    detected_counts: dict[str, int] = {}

    for job in jobs:
        description = job.get("description")
        lang = detect_language(description)
        job["language"] = lang

        detected_counts[lang] = detected_counts.get(lang, 0) + 1

    logger.info("Language detection results: %s", detected_counts)
    return jobs
