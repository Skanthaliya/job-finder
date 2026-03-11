"""
processing/language_detector.py — Job language requirement detection.

Detects both:
1. What language the job description is WRITTEN in (text language)
2. What language the job REQUIRES you to speak (job requirement)

The "language" field reflects the WORKING language requirement,
which is what job seekers actually care about.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Ensure reproducible langdetect results
try:
    from langdetect import detect, DetectorFactory, LangDetectException
    DetectorFactory.seed = 0
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False
    logger.warning("langdetect not installed. Language detection will be limited.")


# =========================================================================
# Keyword patterns for language REQUIREMENT detection
# =========================================================================

# Patterns: GERMAN IS REQUIRED (job needs German to work there)
GERMAN_REQUIRED_PATTERNS = [
    # English text, German explicitly required
    r"german\s+(is\s+)?(required|mandatory|essential|necessary|must|needed)",
    r"(fluent|native|proficient|excellent|strong|advanced)\s+(in\s+)?german",
    r"(must|need\s+to|should)\s+(speak|know|have)\s+german",
    r"german\s+(c1|c2|b2|native|fluency|fluent)",
    r"(c1|c2)\s+(level\s+)?(in\s+)?german",
    r"working\s+language.*german",
    r"german[\s-]speaking\s+(required|essential|mandatory|only)",
    r"requires?\s+german",
    # German text indicating German required
    r"(flie[ßs]ende?|sehr\s+gute|verhandlungssichere?)\s+deutsch",
    r"deutsch(kenntnisse)?\s+(erforderlich|vorausgesetzt|zwingend|notwendig|m[üu]ssen)",
    r"muttersprach(e|lich)\s+deutsch",
    r"deutsch\s+(c1|c2|b2|muttersprachlich)",
    r"(arbeitssprache|unternehmenssprache).*deutsch",
    r"sichere\s+deutschkenntnisse",
    r"deutsch\s+in\s+wort\s+und\s+schrift",
]

# Patterns: GERMAN IS OPTIONAL (nice to have, not blocking)
GERMAN_OPTIONAL_PATTERNS = [
    r"german\s+(is\s+)?(a\s+)?(plus|bonus|advantage|beneficial|nice|preferred|helpful|asset|welcome|desirable)",
    r"(ideally|preferably|optionally).*german",
    r"german.*not\s+(required|mandatory|necessary|essential)",

    r"german\s+(helpful|advantageous)\s+but\s+not\s+(required|essential|mandatory)",
    r"deutsch(kenntnisse)?\s+(von\s+vorteil|w[üu]nschenswert|hilfreich|vorteilhaft|willkommen)",
    r"german\s+is\s+not\s+(required|a\s+must|necessary)",
    r"german\s+language\s+skills\s+are\s+(a\s+)?(plus|bonus|advantage)",
]

# Patterns: ENGLISH IS THE WORKING LANGUAGE
ENGLISH_WORKING_PATTERNS = [
    r"(working|company|team|office|corporate)\s+language.*english",
    r"english[\s-]speaking\s+(environment|team|company|office|workplace)",
    r"(all|our)\s+(communication|meetings|work).*in\s+english",
    r"english\s+(is\s+)?(the\s+)?(working|official|primary|main)\s+language",
    r"no\s+german\s+(required|needed|necessary)",
    r"international\s+(team|environment|company).*english",
    r"without\s+(any\s+)?german",
]

# Title patterns suggesting German-language job
GERMAN_TITLE_PATTERNS = [
    r"\(m/w/d\)", r"\(w/m/d\)", r"\(m/w/x\)", r"\(w/m/x\)",
    r"bundesweit", r"stellenangebot", r"sachbearbeiter",
    r"fachinformatiker", r"kaufmann", r"kauffrau",
    r"werkstudent", r"praktikant", r"auszubildende",
    r"referent(in)?", r"teamleiter(in)?",
]



def detect_language(text: Optional[str], title: str = "") -> str:
    """
    Detect the language requirement of a job posting.

    Returns one of:
    - "English" — English job, no German required
    - "German" — German required or written in German
    - "English (German plus)" — English job, German is nice-to-have
    - "French", "Spanish", etc. — other languages
    - "unknown" — can't determine
    """
    if not text or not isinstance(text, str):
        return _detect_from_title(title)

    text_lower = text.lower()

    # Pre-check: explicit "no German" phrases override any german_required matches
    # (prevents "no German needed" from triggering the german_required pattern)
    no_german_explicit = bool(re.search(
        r"no\s+german\s+(required|needed|necessary|skills|language)",
        text_lower
    ))

    # Step 1: Check GERMAN OPTIONAL patterns first
    german_optional = any(re.search(p, text_lower) for p in GERMAN_OPTIONAL_PATTERNS)

    # Step 2: Check GERMAN REQUIRED patterns (excluded when "no german X" is present)
    german_required = (not no_german_explicit) and any(
        re.search(p, text_lower) for p in GERMAN_REQUIRED_PATTERNS
    )

    # Step 3: Check ENGLISH WORKING LANGUAGE patterns
    english_working = any(re.search(p, text_lower) for p in ENGLISH_WORKING_PATTERNS)

    # Step 4: Detect text language with langdetect
    text_lang = _detect_text_language(text)

    # Step 5: Decision logic

    # If text is in German → German job (unless explicitly says English working language)
    if text_lang == "de":
        if english_working:
            return "English (German plus)"
        return "German"

    # Explicit "no German needed" / English working language → English (unless German required)
    if english_working and not german_required:
        return "English"

    # Text is in English — check requirement keywords
    if german_required and not german_optional:
        return "German"

    if german_required and german_optional:
        # Both found — confusing job post. "German plus" is safer
        return "English (German plus)"

    if german_optional:
        return "English (German plus)"

    # No explicit language keywords — use text language
    if text_lang == "en":
        # Check title for German patterns as extra signal
        if title and any(re.search(p, title.lower()) for p in GERMAN_TITLE_PATTERNS):
            return "English (German plus)"  # English desc but German-style title
        return "English"
    elif text_lang == "fr":
        return "French"
    elif text_lang == "es":
        return "Spanish"
    elif text_lang == "nl":
        return "Dutch"

    # Last resort
    return _detect_from_title(title) if title else "unknown"


def _detect_text_language(text: str) -> str:
    """Detect what language the text is written in."""
    if not LANGDETECT_AVAILABLE:
        return "unknown"

    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"\s+", " ", clean).strip()

    if len(clean) < 30:
        return "unknown"

    try:
        return detect(clean)
    except Exception:
        return "unknown"


def _detect_from_title(title: str) -> str:
    """Heuristic language detection from job title alone."""
    if not title:
        return "unknown"

    title_lower = title.lower()
    if any(re.search(p, title_lower) for p in GERMAN_TITLE_PATTERNS):
        return "German"

    return "unknown"


def detect_languages_batch(jobs: list[dict]) -> list[dict]:
    """
    Detect language requirements for a batch of jobs.
    Updates the 'language' field on each job dict.
    """
    logger.info("Detecting languages for %d jobs...", len(jobs))

    results: dict[str, int] = {}

    for job in jobs:
        desc = job.get("description") or ""
        title = job.get("title") or ""
        lang = detect_language(desc, title)
        job["language"] = lang
        results[lang] = results.get(lang, 0) + 1

    logger.info("Language detection results: %s", results)
    return jobs

