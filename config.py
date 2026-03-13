"""
config.py — Central configuration for the Job Finder tool.

All constants, search defaults, dork templates, ATS patterns, and HTTP settings
are defined here. Import from this module throughout the project.
"""

import os

# Load .env file if it exists (for API keys)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed — use env vars directly

# =============================================================================
# Search Defaults
# =============================================================================
DEFAULT_SEARCH_TERM = "Product Owner"  # Legacy single-term (kept for compat)
DEFAULT_SEARCH_TERMS = [
    "Product Owner",
    "Junior Product Owner",
    "Product Manager",
    "Junior Product Manager",
    "Project Manager",
    "Junior Project Manager",
    "Scrum Master",
    "Junior Scrum Master",
    "Business Analyst",
    "IT Business Analyst",
    "Graduate IT",
    "Business Informatics",
]
DEFAULT_LOCATION = ""  # Empty = whole country (used with Country scope)
DEFAULT_LOCATION_SCOPE = "Country"  # Default scope: Country (not City)
DEFAULT_COUNTRY = "Germany"
DEFAULT_HOURS_OLD = 168  # 7 days
DEFAULT_RESULTS_PER_SITE = 50

# =============================================================================
# Location Scope
# =============================================================================
LOCATION_SCOPE_OPTIONS = ["City", "Country", "Europe"]

EUROPEAN_COUNTRIES = [
    "Germany", "Austria", "Switzerland", "Netherlands", "Belgium",
    "France", "UK", "Ireland", "Sweden", "Denmark", "Norway",
    "Finland", "Spain", "Italy", "Portugal", "Poland",
    "Czech Republic", "Luxembourg", "Estonia", "Latvia", "Lithuania",
]

# =============================================================================
# SerpAPI (optional — free tier: 100 searches/month)
# =============================================================================
SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")

# =============================================================================
# JobSpy Sites
# =============================================================================
JOBSPY_SITES = ["indeed", "linkedin", "google", "glassdoor", "zip_recruiter"]

# =============================================================================
# Google Dorking
# =============================================================================
# Time filter params for Google URL
GOOGLE_TIME_FILTERS = {
    "last_24h": "qdr:d",
    "last_3_days": "qdr:d3",
    "last_7_days": "qdr:w",
    "last_14_days": "qdr:m",   # closest approximation
    "last_30_days": "qdr:m",
}

# Delay between Google dork queries (seconds) to avoid rate limiting
GOOGLE_DORK_DELAY_MIN = 4
GOOGLE_DORK_DELAY_MAX = 9

# Maximum results per dork query
GOOGLE_DORK_RESULTS_PER_QUERY = 30

# =============================================================================
# ATS URL Patterns (regex) for URL Router
# =============================================================================
ATS_PATTERNS = {
    "workday": r"[\w-]+\.wd\d+\.myworkdayjobs\.com",
    "greenhouse": r"boards\.greenhouse\.io/([\w-]+)",
    "lever": r"jobs\.lever\.co/([\w-]+)",
    "personio": r"([\w-]+)\.jobs\.personio\.de",
    "ashby": r"jobs\.ashbyhq\.com/([\w-]+)",
    "smartrecruiters": r"jobs\.smartrecruiters\.com/([\w-]+)",
    "icims": r"careers[\w-]*\.icims\.com",
    "taleo": r"[\w-]+\.taleo\.net",
}

# =============================================================================
# Google Dork Templates
# =============================================================================
# {keyword} and {location} are replaced at runtime
DORK_TEMPLATES = [
    # Tier 1: Major ATS platforms
    'site:myworkdayjobs.com "{keyword}" "{location}"',
    'site:boards.greenhouse.io "{keyword}" "{location}"',
    'site:jobs.lever.co "{keyword}" "{location}"',
    'site:jobs.ashbyhq.com "{keyword}" "{location}"',
    'site:jobs.smartrecruiters.com "{keyword}" "{location}"',
    'site:jobs.personio.de "{keyword}" "{location}"',
    # Tier 2: More ATS platforms
    'site:icims.com "{keyword}" "{location}"',
    'site:taleo.net "{keyword}" "{location}"',
    'site:recruiting.paylocity.com "{keyword}" "{location}"',
    'site:breezy.hr "{keyword}" "{location}"',
    # Tier 3: Wild discovery — direct company career pages
    'inurl:careers "{keyword}" "{location}" -site:linkedin.com -site:indeed.com -site:glassdoor.com',
    'inurl:/jobs/ "{keyword}" "{location}" -site:linkedin.com -site:indeed.com -site:glassdoor.com',
    'intitle:"careers" "{keyword}" "{location}" -site:linkedin.com -site:indeed.com',
    # English-specific dorks
    'site:myworkdayjobs.com "{keyword}" "{location}" "English"',
    'site:boards.greenhouse.io "{keyword}" "{location}" "English"',
]

# Additional language-specific dork templates
ENGLISH_EXTRA_DORKS = [
    '"{keyword}" "{location}" "no German required"',
    '"{keyword}" "{location}" "English speaking" careers',
    '"{keyword}" "{location}" "international team" inurl:jobs',
]

GERMAN_EXTRA_DORKS = [
    '"{keyword}" "{location}" "Deutschkenntnisse" Karriere',
    '"{keyword}" "{location}" "Stellenangebot"',
]

# =============================================================================
# HTTP Settings
# =============================================================================
REQUEST_TIMEOUT = 30
MAX_RETRIES = 2
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

# =============================================================================
# Output
# =============================================================================
OUTPUT_DIR = "output"

# =============================================================================
# Logging
# =============================================================================
LOG_FILE = "job_finder.log"
LOG_LEVEL = "INFO"

# =============================================================================
# AI / Gemini
# =============================================================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.0-flash"
PROFILE_PATH = "my_profile.json"
PROFILE_TXT_PATH = "my_profile.txt"
COVER_LETTER_PROMPT_PATH = "cover_letter_prompt.txt"
GEMINI_RATE_LIMIT_DELAY = 4.0  # seconds between API calls (safe for 15 RPM free tier)
GEMINI_BATCH_SIZE = 5

# =============================================================================
# Country list for GUI dropdown
# =============================================================================
COUNTRIES = [
    "Germany",
    "USA",
    "UK",
    "Austria",
    "Switzerland",
    "Netherlands",
    "France",
    "Canada",
    "Australia",
    "Ireland",
    "Sweden",
    "Denmark",
    "Norway",
    "Finland",
    "Belgium",
    "Spain",
    "Italy",
    "Portugal",
    "Poland",
    "Czech Republic",
    "Singapore",
    "India",
    "Japan",
    "Remote / Worldwide",
]

# =============================================================================
# Time filter options for GUI
# =============================================================================
TIME_FILTER_OPTIONS = {
    "Last 24 hours": 24,
    "Last 3 days": 72,
    "Last 7 days": 168,
    "Last 14 days": 336,
    "Last 30 days": 720,
}

# =============================================================================
# Job type options
# =============================================================================
JOB_TYPE_OPTIONS = ["Any", "fulltime", "parttime", "contract", "internship"]

# =============================================================================
# Language filter options
# =============================================================================
LANGUAGE_FILTER_OPTIONS = [
    "All",
    "English",
    "English (German plus)",
    "German",
    "French",
    "Spanish",
]
