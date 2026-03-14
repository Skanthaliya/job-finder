"""
processing/language_detector.py — Job language detection (dual-field).

Detects TWO separate things for each job:

1. ``listing_language`` — What language the job description TEXT is written in.
   Detected purely via ``langdetect`` on the description text.
   Values: "English", "German", "French", "Spanish", "Hindi", "Dutch", etc.

2. ``language_required`` — What language the job REQUIRES you to speak.
   Detected via regex patterns on description + title, looking for explicit
   statements like "German required", "fluent English", "(m/w/d)", etc.
   Values: "English", "German", "English (German plus)", "French", "Hindi", etc.

The legacy ``language`` field is kept for backwards compatibility and is set
to ``language_required`` (since that's what job seekers filter on).
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

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

GERMAN_REQUIRED_PATTERNS = [
    r"german\s+(is\s+)?(required|mandatory|essential|necessary|must|needed)",
    r"(fluent|native|proficient|excellent|strong|advanced)\s+(in\s+)?german",
    r"(must|need\s+to|should)\s+(speak|know|have)\s+german",
    r"german\s+(c1|c2|b2|native|fluency|fluent)",
    r"(c1|c2)\s+(level\s+)?(in\s+)?german",
    r"working\s+language.*german",
    r"german[\s-]speaking\s+(required|essential|mandatory|only)",
    r"requires?\s+german",
    r"(flie[ßs]ende?|sehr\s+gute|verhandlungssichere?)\s+deutsch",
    r"deutsch(kenntnisse)?\s+(erforderlich|vorausgesetzt|zwingend|notwendig|m[üu]ssen)",
    r"muttersprach(e|lich)\s+deutsch",
    r"deutsch\s+(c1|c2|b2|muttersprachlich)",
    r"(arbeitssprache|unternehmenssprache).*deutsch",
    r"sichere\s+deutschkenntnisse",
    r"deutsch\s+in\s+wort\s+und\s+schrift",
    r"german[\s-]speaker",
    r"native[\s-]level\s+german",
    r"business[\s-]level\s+german",
    r"professional[\s-]level\s+german",
    r"german\s+native\s+speaker",
    r"mother[\s-]tongue.*german",
    r"german.*mother[\s-]tongue",
    r"native[\s-]german",
    r"confident\s+(business\s+)?german",
    r"conversational\s+german",
    r"(good|solid|strong)\s+command\s+of\s+german",
    r"german\s+(skills?\s+)?(required|needed|essential|mandatory)",
    r"(speak|speaking)\s+german",
    r"german\s+(b1|b2|c1|c2)[\s-]level",
    r"(b1|b2|c1|c2)[\s-]level\s+(in\s+)?german",
    r"german\s+language\s+(required|needed|skills|proficiency)",
    r"deutsch\s+als\s+arbeitssprache",
    r"gute\s+deutschkenntnisse",
    r"deutschkenntnisse\s+(auf\s+)?(c1|c2|b2|muttersprachniveau)",
    r"sprache[n]?:\s*deutsch",
    r"verhandlungssicher(es?)?\s+deutsch",
    r"deutsch\s+verhandlungssicher",
    r"kommunikation(sf[äa]higkeit)?\s+in\s+deutsch",
    r"german\s+at\s+(a\s+)?(native|business|professional|fluent)\s+level",
    r"(mindestens|minimum)\s+(b2|c1|c2)\s+(in\s+)?german",
    r"(mindestens|minimum)\s+(b2|c1|c2)\s+(in\s+)?deutsch",
]

GERMAN_OPTIONAL_PATTERNS = [
    r"german\s+(is\s+)?(a\s+)?(plus|bonus|advantage|beneficial|nice|preferred|helpful|asset|welcome|desirable)",
    r"(ideally|preferably|optionally).*german",
    r"german.*not\s+(required|mandatory|necessary|essential)",
    r"german\s+(helpful|advantageous)\s+but\s+not\s+(required|essential|mandatory)",
    r"deutsch(kenntnisse)?\s+(von\s+vorteil|w[üu]nschenswert|hilfreich|vorteilhaft|willkommen)",
    r"german\s+is\s+not\s+(required|a\s+must|necessary)",
    r"german\s+language\s+skills\s+are\s+(a\s+)?(plus|bonus|advantage)",
    r"(basic|some|elementary)\s+german",
    r"german\s+(a1|a2|b1)\b",
    r"willingness\s+to\s+learn\s+german",
    r"german\s+is\s+(nice|good)\s+to\s+have",
    r"(bonus|plus)\s*:\s*german",
    r"open\s+to\s+learning\s+german",
    r"bereitschaft\s+deutsch\s+zu\s+lernen",
]

ENGLISH_WORKING_PATTERNS = [
    r"(working|company|team|office|corporate)\s+language.*english",
    r"english[\s-]speaking\s+(environment|team|company|office|workplace)",
    r"(all|our)\s+(communication|meetings|work).*in\s+english",
    r"english\s+(is\s+)?(the\s+)?(working|official|primary|main)\s+language",
    r"no\s+german\s+(required|needed|necessary)",
    r"international\s+(team|environment|company).*english",
    r"without\s+(any\s+)?german",
    r"englisch\s+(ist\s+)?(die\s+)?(arbeitssprache|unternehmenssprache)",
    r"(fluent|proficient|excellent)\s+english\s+(is\s+)?(required|mandatory|essential)",
    r"english\s+(c1|c2|native)\s+(required|level)",
    r"communicate\s+(effectively\s+)?in\s+english",
    r"english\s+only\s+(environment|team|workplace)",
]

ENGLISH_REQUIRED_PATTERNS = [
    r"english\s+(is\s+)?(required|mandatory|essential|necessary|must|needed)",
    r"(fluent|native|proficient|excellent|strong)\s+(in\s+)?english",
    r"(must|need\s+to|should)\s+(speak|know|have)\s+english",
    r"english\s+(c1|c2|b2|native|fluency|fluent)",
    r"english[\s-]speaking\s+(required|essential|mandatory)",
    r"english\s+language\s+(required|needed|skills|proficiency)",
    r"(good|excellent|strong)\s+command\s+of\s+english",
    r"english\s+communication\s+skills",
]

FRENCH_REQUIRED_PATTERNS = [
    r"french\s+(is\s+)?(required|mandatory|essential|necessary|needed)",
    r"(fluent|native|proficient|excellent)\s+(in\s+)?french",
    r"(must|need\s+to)\s+(speak|know|have)\s+french",
    r"french\s+(c1|c2|b2|native|fluent)",
    r"french[\s-]speaking\s+(required|essential|mandatory)",
    r"fran[çc]ais\s+(requis|obligatoire|indispensable|courant)",
    r"ma[îi]trise\s+du\s+fran[çc]ais",
    r"langue\s+de\s+travail.*fran[çc]ais",
]

DUTCH_REQUIRED_PATTERNS = [
    r"dutch\s+(is\s+)?(required|mandatory|essential|necessary|needed)",
    r"(fluent|native|proficient|excellent)\s+(in\s+)?dutch",
    r"(must|need\s+to)\s+(speak|know|have)\s+dutch",
    r"dutch\s+(c1|c2|b2|native|fluent)",
    r"dutch[\s-]speaking\s+(required|essential|mandatory)",
    r"nederlands\s+(vereist|verplicht|noodzakelijk|vloeiend)",
    r"vloeiend\s+nederlands",
]

HINDI_REQUIRED_PATTERNS = [
    r"hindi\s+(is\s+)?(required|mandatory|essential|necessary|needed)",
    r"(fluent|native|proficient)\s+(in\s+)?hindi",
    r"(must|need\s+to)\s+(speak|know|have)\s+hindi",
    r"hindi[\s-]speaking\s+(required|essential|mandatory)",
    r"hindi\s+language\s+(required|needed|skills)",
    r"(speak|speaking)\s+hindi",
    r"regional\s+language.*hindi",
]

GERMAN_TITLE_PATTERNS = [
    r"\(m/w/d\)", r"\(w/m/d\)", r"\(m/w/x\)", r"\(w/m/x\)",
    r"\(m/f/d\)", r"\(f/m/d\)", r"\(m/f/x\)",
    r"bundesweit", r"stellenangebot", r"sachbearbeiter",
    r"fachinformatiker", r"kaufmann", r"kauffrau",
    r"werkstudent", r"praktikant", r"auszubildende",
    r"referent(in)?", r"teamleiter(in)?",
    r"german[\s-]speak", r"deutschsprachig",
    r"german[\s-]native", r"muttersprachler",
    r"german\s+required", r"deutsch\s+erforderlich",
    r"deu?tschland",
    r"projektleiter(in)?", r"produktmanager(in)?",
    r"gesch[äa]ftsf[üu]hrer(in)?", r"berater(in)?",
    r"entwickler(in)?", r"ingenieur(in)?",
    r"mitarbeiter(in)?", r"leiter(in)?",
    r"fachkraft", r"spezialist(in)?",
    r"vollzeit", r"teilzeit",
    r"festanstellung", r"befristet",
    r"standort\s*:", r"ab\s+sofort",
]

# Map langdetect ISO codes to human-readable names
_LANG_CODE_MAP = {
    "en": "English",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "nl": "Dutch",
    "pt": "Portuguese",
    "it": "Italian",
    "hi": "Hindi",
    "ja": "Japanese",
    "zh-cn": "Chinese",
    "ko": "Korean",
    "ar": "Arabic",
    "ru": "Russian",
    "pl": "Polish",
    "sv": "Swedish",
    "da": "Danish",
    "no": "Norwegian",
    "fi": "Finnish",
}


def detect_listing_language(text: Optional[str]) -> str:
    """Detect what language the description text is written in.

    Returns a human-readable language name like "English", "German", etc.
    """
    if not text or not isinstance(text, str):
        return "unknown"

    if not LANGDETECT_AVAILABLE:
        return "unknown"

    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"\s+", " ", clean).strip()

    if len(clean) < 30:
        return "unknown"

    try:
        code = detect(clean)
        return _LANG_CODE_MAP.get(code, code)
    except Exception:
        return "unknown"


def detect_language_required(text: Optional[str], title: str = "") -> str:
    """Detect what language the job REQUIRES you to speak.

    Analyses the description and title for explicit language requirement
    statements. Returns one of:
    - "English" — English-only, no other language required
    - "German" — German required
    - "English (German plus)" — English job, German is nice-to-have
    - "French", "Dutch", "Hindi", etc.
    - "unknown" — can't determine from text
    """
    if not text or not isinstance(text, str):
        return _detect_requirement_from_title(title)

    text_lower = text.lower()

    no_german_explicit = bool(re.search(
        r"no\s+german\s+(required|needed|necessary|skills|language)",
        text_lower,
    ))

    german_optional = any(re.search(p, text_lower) for p in GERMAN_OPTIONAL_PATTERNS)
    german_required = (not no_german_explicit) and any(
        re.search(p, text_lower) for p in GERMAN_REQUIRED_PATTERNS
    )
    english_working = any(re.search(p, text_lower) for p in ENGLISH_WORKING_PATTERNS)
    english_required = any(re.search(p, text_lower) for p in ENGLISH_REQUIRED_PATTERNS)

    # Detect text language as a signal
    text_lang = detect_listing_language(text)

    # If text is in German → German job (unless explicitly says English working language)
    if text_lang == "German":
        if english_working:
            return "English (German plus)"
        return "German"

    # Explicit "no German needed" / English working language
    if english_working and not german_required:
        return "English"

    if german_required and not german_optional:
        return "German"

    if german_required and german_optional:
        return "English (German plus)"

    if german_optional:
        return "English (German plus)"

    # Check other languages
    french_required = any(re.search(p, text_lower) for p in FRENCH_REQUIRED_PATTERNS)
    if french_required:
        return "French"

    dutch_required = any(re.search(p, text_lower) for p in DUTCH_REQUIRED_PATTERNS)
    if dutch_required:
        return "Dutch"

    hindi_required = any(re.search(p, text_lower) for p in HINDI_REQUIRED_PATTERNS)
    if hindi_required:
        return "Hindi"

    # English required explicitly
    if english_required:
        return "English"

    # No explicit keywords — infer from text language and title
    if text_lang == "English":
        if title:
            title_lower = title.lower()
            if any(re.search(p, title_lower) for p in GERMAN_REQUIRED_PATTERNS):
                return "German"
            if any(re.search(p, title_lower) for p in GERMAN_TITLE_PATTERNS):
                return "English (German plus)"
        return "English"
    elif text_lang == "French":
        return "French"
    elif text_lang == "Spanish":
        return "Spanish"
    elif text_lang == "Dutch":
        return "Dutch"
    elif text_lang == "Hindi":
        return "Hindi"

    return _detect_requirement_from_title(title) if title else "unknown"


def _detect_requirement_from_title(title: str) -> str:
    """Heuristic language requirement detection from job title alone."""
    if not title:
        return "unknown"

    title_lower = title.lower()
    if any(re.search(p, title_lower) for p in GERMAN_TITLE_PATTERNS):
        return "German"

    return "unknown"


# Legacy compatibility alias
def detect_language(text: Optional[str], title: str = "") -> str:
    """Legacy function — returns the language_required value."""
    return detect_language_required(text, title)


def detect_languages_batch(jobs: list[dict]) -> list[dict]:
    """Detect languages for a batch of jobs.

    Populates three fields on each job dict:
    - ``listing_language``: what language the description is written in
    - ``language_required``: what language the job requires you to speak
    - ``language``: same as language_required (backwards compatibility)
    """
    logger.info("Detecting languages for %d jobs...", len(jobs))

    listing_stats: dict[str, int] = {}
    required_stats: dict[str, int] = {}

    for job in jobs:
        desc = job.get("description") or ""
        title = job.get("title") or ""

        listing_lang = detect_listing_language(desc)
        required_lang = detect_language_required(desc, title)

        job["listing_language"] = listing_lang
        job["language_required"] = required_lang
        job["language"] = required_lang  # backwards compat

        listing_stats[listing_lang] = listing_stats.get(listing_lang, 0) + 1
        required_stats[required_lang] = required_stats.get(required_lang, 0) + 1

    logger.info("Listing language stats: %s", listing_stats)
    logger.info("Required language stats: %s", required_stats)
    return jobs
