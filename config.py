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
HOURS_IN_YEAR = 8760
SCRAPER_TIMEOUT = 300  # 5-minute timeout per scraper

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
# Location Filter Data
# =============================================================================
GERMAN_CITIES = [
    "berlin", "munich", "münchen", "hamburg", "frankfurt",
    "cologne", "köln", "düsseldorf", "stuttgart", "dresden",
    "leipzig", "hannover", "nuremberg", "nürnberg", "dortmund",
    "essen", "bremen", "bonn", "mannheim", "karlsruhe",
    "freiburg", "heidelberg", "mainz", "wiesbaden", "potsdam",
    "rostock", "kiel", "augsburg", "aachen", "regensburg",
    "darmstadt", "wolfsburg", "ingolstadt", "ulm", "bielefeld",
]

INDIAN_CITIES = [
    "bangalore", "bengaluru", "mumbai", "hyderabad", "pune",
    "delhi", "new delhi", "ncr", "delhi ncr", "gurgaon", "gurugram",
    "noida", "greater noida", "ghaziabad", "faridabad",
    "chennai", "kolkata", "ahmedabad", "jaipur", "lucknow",
    "kochi", "cochin", "thiruvananthapuram", "trivandrum",
    "chandigarh", "indore", "bhopal", "nagpur", "coimbatore",
    "visakhapatnam", "vizag", "mysore", "mysuru", "mangalore",
    "mangaluru", "vadodara", "surat", "rajkot", "gandhinagar",
    "bhubaneswar", "patna", "ranchi", "dehradun", "shimla",
    "goa", "panaji", "pondicherry", "puducherry",
]

ALLOWED_REMOTE_COUNTRIES = [
    "germany", "austria", "switzerland", "netherlands", "belgium",
    "france", "uk", "united kingdom", "ireland", "sweden", "denmark",
    "norway", "finland", "spain", "italy", "portugal", "poland",
    "czech republic", "luxembourg", "estonia", "latvia", "lithuania",
    "india", "europe", "eu", "emea", "eea", "dach",
]

GLOBAL_REMOTE_KEYWORDS = [
    "worldwide", "anywhere", "global", "work from anywhere",
    "fully remote", "100% remote", "remote-first",
]

BLOCKED_REMOTE_COUNTRIES = [
    "united states", "usa", "u.s.", "us only",
    "canada only", "australia only", "japan only",
    "china only", "korea only", "brazil only",
    "latin america", "latam only",
]

# =============================================================================
# SerpAPI (optional — free tier: 100 searches/month)
# =============================================================================
SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")

# =============================================================================
# JobSpy Sites
# =============================================================================
JOBSPY_SITES = ["indeed", "linkedin", "google", "glassdoor", "zip_recruiter", "naukri", "bayt"]

# Country-specific site recommendations (auto-enabled when country matches)
COUNTRY_JOBSPY_SITES = {
    "India": ["indeed", "linkedin", "google", "glassdoor", "naukri"],
    "UAE": ["indeed", "linkedin", "google", "bayt"],
    "Saudi Arabia": ["indeed", "linkedin", "google", "bayt"],
    "Qatar": ["indeed", "linkedin", "google", "bayt"],
    "Bahrain": ["indeed", "linkedin", "google", "bayt"],
    "Kuwait": ["indeed", "linkedin", "google", "bayt"],
    "Oman": ["indeed", "linkedin", "google", "bayt"],
}

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

INDIA_EXTRA_DORKS = [
    'site:naukri.com "{keyword}" "{location}"',
    'site:foundit.in "{keyword}" "{location}"',
    'site:instahyre.com "{keyword}" "{location}"',
    'site:cutshort.io "{keyword}" "{location}"',
    '"{keyword}" "{location}" "hiring" site:linkedin.com/jobs India',
    '"{keyword}" "{location}" careers -site:naukri.com -site:linkedin.com -site:indeed.com',
    'inurl:careers "{keyword}" "{location}" India',
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
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_MODEL_OPTIONS = ["gemini-2.5-flash", "gemini-2.0-flash"]
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
    "India",
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
    "Japan",
    "UAE",
    "Saudi Arabia",
    "Qatar",
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
    "Hindi",
]
