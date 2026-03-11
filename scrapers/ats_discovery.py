"""
scrapers/ats_discovery.py — Direct ATS API job discovery.

Queries Greenhouse, Lever, Ashby, SmartRecruiters APIs
directly using company slug lists. No Google needed.

Sources for company slugs:
1. Built-in curated list (120+ companies)
2. Auto-discovered companies (from company_registry.json)
3. SerpAPI-discovered URLs (when API key is configured)
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

logger = logging.getLogger(__name__)

# =========================================================================
# Curated company lists — Berlin/Germany/Europe focused + major global
# =========================================================================

GREENHOUSE_COMPANIES = [
    # Germany / Berlin startups & tech
    "contentful", "personio", "trade-republic", "hellofresh",
    "westwing", "thermondo", "taxfix", "mambu", "raisin",
    "wefox", "solarisbank", "n26", "babbel", "adjust",
    "signavio", "celonis", "deliveryhero", "wayfair",
    "zalando", "moonfare", "omio", "soundcloud", "idealo",
    "flixbus", "jimdo", "ecosia", "forto", "grover",
    "tier-mobility", "infarm", "comtravo", "scout24",
    "auto1-group", "smava", "finleap", "billie", "moss",
    "agicap", "factorial", "leapsome", "kenjo",
    # EU companies
    "klarna", "adyen", "mollie", "messagebird", "miro",
    "productboard", "typeform", "storyblok", "pitch",
    "doctolib", "backmarket", "qonto", "alan",
    "scaleway", "ovhcloud", "blablacar", "deezer",
    "trivago", "check24", "aboutyou", "ottonow",
    "sixt", "flixmobility", "mytheresa", "limehome",
    # Global tech (hiring in Europe)
    "toast", "figma", "cloudflare", "datadog", "plaid",
    "stripe", "gitlab", "zapier", "notion", "linear",
    "airbnb", "spotify", "twilio", "hubspot",
    "mongodb", "elastic", "hashicorp", "grafana",
    "aiven", "confluent", "snyk", "sentry",
    "cockroachlabs", "supabase", "vercel", "netlify",
    "render", "remote", "deel", "oyster",
    "pleo", "moss-carbon", "circula",
]

LEVER_COMPANIES = [
    "Netflix", "anthropic", "figma", "notion",
    "netlify", "webflow", "postman", "airtable",
    "brex", "rippling", "gusto", "ramp",
    "databricks", "scale", "replit", "vercel",
    "gorillas", "flink", "wolt", "getir",
    "klarna", "adyen", "mollie", "sumup",
    "wise", "revolut", "monzo", "starling",
    "messagebird", "miro", "productboard",
    "typeform", "aiven", "storyblok",
    "pitch", "rows", "wonder",
    "personio", "contentful", "commercetools",
    "celonis", "babbel", "adjust",
    "sennder", "forto", "freighthub",
    "lilium", "volocopter", "isar-aerospace",
]

ASHBY_COMPANIES = [
    "anthropic", "ramp", "notion", "linear",
    "vercel", "retool", "loom", "sourcegraph",
    "deel", "remote", "oyster", "lattice",
    "dbt-labs", "airbyte", "rudderstack",
    "hightouch", "census", "fivetran",
    "vanta", "drata", "snorkel-ai",
    "cohere", "together-ai", "replit",
    "codeium", "cursor", "mistral",
]

SMARTRECRUITERS_COMPANIES = [
    "Visa", "Bosch", "IKEA", "Sanofi",
    "CocaCola", "Equinix", "LinkedIn",
    "Square", "Etsy", "Deloitte",
    "Accenture", "CapGemini", "Atos",
    "DeutschePost", "DHL", "Siemens",
    "Continental", "Infineon", "SAP",
]

PERSONIO_COMPANIES = [
    # German startups & SMEs using Personio
    "flixbus", "thermondo", "urbanara", "comtravo",
    "grover", "infarm", "tier-mobility", "gorillas",
    "flink", "getir", "wolt", "foodspring",
    "jimdo", "eyeo", "adjust", "contentful",
    "signavio", "mambu", "raisin", "smava",
    "homeday", "helpling", "kreditech", "fincompare",
    "medwing", "kenjo", "leapsome", "moss",
    "circula", "pleo", "agicap", "factorial",
    "personio", "recruitee", "softgarden", "rexx-systems",
    "haufe-lexware", "datev", "teamviewer", "celonis",
    "tonies", "about-you", "otto-group", "mytheresa",
    "limehome", "klarx", "forto", "sennder",
    "lilium", "isar-aerospace", "volocopter",
    "enpal", "1komma5", "klima", "planetly",
]

# Workday requires full base URLs — can't be guessed from slug alone
# Format: "Company Name" -> "base URL for Workday jobs API"
# These are FREE to query — no API key, no signup needed
WORKDAY_CAREER_URLS = {
    # German DAX / major German companies
    "Siemens": "https://siemens.wd3.myworkdayjobs.com/en-US/External",
    "SAP": "https://sap.wd1.myworkdayjobs.com/en-US/SAPCareers",
    "BMW": "https://bmw.wd3.myworkdayjobs.com/en/BMW_Careers",
    "Allianz": "https://allianz.wd3.myworkdayjobs.com/en-US/Allianz",
    "Deutsche Bank": "https://db.wd3.myworkdayjobs.com/en-US/DBWebsite",
    "Bosch": "https://bosch.wd3.myworkdayjobs.com/en-US/BoschCareers",
    "Mercedes-Benz": "https://mercedesbenz.wd3.myworkdayjobs.com/en-US/Mercedesbenz",
    "Bayer": "https://bayer.wd3.myworkdayjobs.com/en-US/BayerCareer",
    "BASF": "https://basf.wd3.myworkdayjobs.com/en-US/BASFCareers",
    "Deutsche Telekom": "https://telekom.wd3.myworkdayjobs.com/en-US/External",
    "Henkel": "https://henkel.wd3.myworkdayjobs.com/en-US/Henkel",
    "Continental": "https://continental.wd3.myworkdayjobs.com/en-US/ExternalCareerSite",
    "Infineon": "https://infineon.wd3.myworkdayjobs.com/en-US/Infineon",
    "Volkswagen": "https://volkswagen.wd3.myworkdayjobs.com/en-US/Volkswagen",
    # European
    "Philips": "https://philips.wd3.myworkdayjobs.com/en-US/jobs_philips",
    "Unilever": "https://unilever.wd3.myworkdayjobs.com/en-US/Unilever",
    "Roche": "https://roche.wd3.myworkdayjobs.com/en-US/roche-ext",
    "Novartis": "https://novartis.wd3.myworkdayjobs.com/en-US/Novartis_Careers",
    "ABB": "https://abb.wd3.myworkdayjobs.com/en-US/ABB",
    "Ericsson": "https://ericsson.wd3.myworkdayjobs.com/en-US/Ericsson",
    # US tech (hiring in Europe)
    "Salesforce": "https://salesforce.wd12.myworkdayjobs.com/en-US/External_Career_Site",
    "Adobe": "https://adobe.wd5.myworkdayjobs.com/en-US/external_experienced",
    "Intel": "https://intel.wd1.myworkdayjobs.com/en-US/External",
    "PayPal": "https://paypal.wd1.myworkdayjobs.com/en-US/jobs",
    "Mastercard": "https://mastercard.wd1.myworkdayjobs.com/en-US/CorporateCareers",
    "ServiceNow": "https://servicenow.wd1.myworkdayjobs.com/en-US/Careers",
    "Workday": "https://workday.wd5.myworkdayjobs.com/en-US/Workday",
    "Oracle": "https://oracle.wd1.myworkdayjobs.com/en-US/Careers",
    "IBM": "https://ibm.wd5.myworkdayjobs.com/en-US/IBM_Careers",
    "Cisco": "https://cisco.wd5.myworkdayjobs.com/en-US/External",
    "Dell": "https://dell.wd1.myworkdayjobs.com/en-US/External",
}


def discover_and_scrape(
    search_terms: list[str],
    location: str = "",
    search_locations: list[str] | None = None,
    hours_old: int = 720,
    max_companies_per_ats: int = 200,
    max_workers: int = 15,
    progress_callback: Callable[[str], None] | None = None,
) -> list[dict]:
    """
    Discover jobs by directly querying ATS platform APIs.

    Args:
        search_terms: List of job titles to search for
        location: Primary location string to filter by
        search_locations: List of locations to match against (for country/Europe scope)
        hours_old: Max job age (for interface compat)
        max_companies_per_ats: Max companies to query per platform
        max_workers: Concurrent API threads
        progress_callback: Optional progress updates
    """

    def _cb(msg):
        logger.info(msg)
        if progress_callback:
            try:
                progress_callback(msg)
            except Exception:
                pass

    # Merge built-in lists with auto-discovered companies
    from scrapers.company_registry import get_discovered_slugs

    gh_companies = list(set(GREENHOUSE_COMPANIES + get_discovered_slugs("greenhouse")))
    lv_companies = list(set(LEVER_COMPANIES + get_discovered_slugs("lever")))
    ab_companies = list(set(ASHBY_COMPANIES + get_discovered_slugs("ashby")))
    sr_companies = list(
        set(SMARTRECRUITERS_COMPANIES + get_discovered_slugs("smartrecruiters"))
    )
    pe_companies = list(set(PERSONIO_COMPANIES + get_discovered_slugs("personio")))

    # Load Workday URLs from registry (previously discovered)
    from scrapers.company_registry import load_registry as _load_reg
    _reg = _load_reg()
    discovered_workday = {}
    for key, val in _reg.get("companies", {}).items():
        if val.get("ats") == "workday" and val.get("url"):
            discovered_workday[val.get("company_name", val["slug"])] = val["url"]

    all_workday = {**WORKDAY_CAREER_URLS, **discovered_workday}

    total_companies = (
        len(gh_companies[:max_companies_per_ats])
        + len(lv_companies[:max_companies_per_ats])
        + len(ab_companies[:max_companies_per_ats])
        + len(sr_companies[:max_companies_per_ats])
        + len(pe_companies[:max_companies_per_ats])
    )

    _cb(f"ATS Discovery: Checking {total_companies} companies + "
        f"{len(all_workday)} Workday career pages across 6 platforms...")

    # Build location filter list
    if search_locations:
        loc_filters = [loc.lower() for loc in search_locations]
    elif location:
        loc_filters = [location.lower()]
    else:
        loc_filters = []  # No location filter = accept all

    all_jobs: list[dict] = []
    start_time = time.time()
    MAX_DISCOVERY_TIME = 120  # 2 minutes max for ATS discovery

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}

        for slug in gh_companies[:max_companies_per_ats]:
            futures[
                executor.submit(
                    _safe_scrape, "greenhouse", slug, search_terms, loc_filters
                )
            ] = f"gh:{slug}"

        for slug in lv_companies[:max_companies_per_ats]:
            futures[
                executor.submit(
                    _safe_scrape, "lever", slug, search_terms, loc_filters
                )
            ] = f"lv:{slug}"

        for slug in ab_companies[:max_companies_per_ats]:
            futures[
                executor.submit(
                    _safe_scrape, "ashby", slug, search_terms, loc_filters
                )
            ] = f"ab:{slug}"

        for slug in sr_companies[:max_companies_per_ats]:
            futures[
                executor.submit(
                    _safe_scrape, "smartrecruiters", slug, search_terms, loc_filters
                )
            ] = f"sr:{slug}"

        for slug in pe_companies[:max_companies_per_ats]:
            futures[
                executor.submit(
                    _safe_scrape, "personio", slug, search_terms, loc_filters
                )
            ] = f"pe:{slug}"

        # --- Workday (requires full URLs, not slugs) ---
        for company_name, base_url in list(all_workday.items())[:max_companies_per_ats]:
            futures[executor.submit(
                _safe_scrape_workday, base_url, company_name, search_terms, loc_filters
            )] = f"wd:{company_name}"

        completed = 0
        total = len(futures)
        companies_with_jobs = 0

        for future in as_completed(futures):
            completed += 1
            label = futures[future]

            if time.time() - start_time > MAX_DISCOVERY_TIME:
                _cb(f"ATS Discovery: Time limit reached ({MAX_DISCOVERY_TIME}s). "
                    f"Stopping with {len(all_jobs)} jobs from {completed}/{total} companies.")
                for f in futures:
                    f.cancel()
                break

            try:
                result = future.result(timeout=30)
                if result:
                    all_jobs.extend(result)
                    companies_with_jobs += 1
                    if len(result) > 0:
                        _cb(f"  ✅ {label}: {len(result)} matching jobs")
            except Exception as e:
                logger.debug("%s failed: %s", label, e)

            if completed % 25 == 0:
                _cb(
                    f"ATS Discovery: {completed}/{total} companies checked, "
                    f"{len(all_jobs)} jobs found..."
                )

    _cb(
        f"ATS Discovery complete: {len(all_jobs)} jobs from "
        f"{companies_with_jobs} companies"
    )

    return all_jobs


def _safe_scrape(
    ats: str, slug: str, search_terms: list[str], loc_filters: list[str]
) -> list[dict]:
    """Safely scrape one company, filtering by multiple search terms and locations."""
    try:
        time.sleep(0.2)  # Small delay to be polite

        if ats == "greenhouse":
            from scrapers.ats.greenhouse import scrape_greenhouse_company

            all_jobs = scrape_greenhouse_company(slug, search_term=None, location=None)
        elif ats == "lever":
            from scrapers.ats.lever import scrape_lever_company

            all_jobs = scrape_lever_company(slug, search_term=None, location=None)
        elif ats == "ashby":
            from scrapers.ats.ashby import scrape_ashby_company

            all_jobs = scrape_ashby_company(slug, search_term=None, location=None)
        elif ats == "smartrecruiters":
            from scrapers.ats.smartrecruiters import scrape_sr_company

            all_jobs = scrape_sr_company(slug, search_term=None, location=None)
        elif ats == "personio":
            from scrapers.ats.personio import scrape_personio_company

            all_jobs = scrape_personio_company(slug, search_term=None, location=None)
        else:
            return []

        if not all_jobs:
            return []

        # Filter by search terms (ANY term must match title)
        matched = []
        search_terms_lower = [t.lower() for t in search_terms]

        for job in all_jobs:
            title = (job.get("title") or "").lower()
            desc = (job.get("description") or "").lower()

            # Check if ANY search term matches
            term_match = False
            for term in search_terms_lower:
                words = term.split()
                # All words of the term must appear in title OR description
                if all(w in title for w in words):
                    term_match = True
                    break
                if all(w in desc for w in words):
                    term_match = True
                    break

            if not term_match:
                continue

            # Check location (if filters set)
            if loc_filters:
                job_loc = (job.get("location") or "").lower()
                loc_match = any(loc in job_loc for loc in loc_filters)
                # Also accept "remote" jobs
                if not loc_match and "remote" not in job_loc:
                    continue

            # Update source to reflect ATS discovery
            job["source"] = "ats_discovery"
            matched.append(job)

        return matched

    except Exception as e:
        logger.debug("%s:%s failed: %s", ats, slug, e)
        return []


def _safe_scrape_workday(
    base_url: str, company_name: str,
    search_terms: list[str], loc_filters: list[str]
) -> list[dict]:
    """Safely scrape a Workday career page using existing workday.py scraper."""
    try:
        time.sleep(0.5)
        from scrapers.ats.workday import scrape_workday_company

        all_jobs = scrape_workday_company(base_url)

        if all_jobs:
            logger.info("Workday %s: %d total jobs fetched from %s", 
                       company_name, len(all_jobs), base_url[:60])
        else:
            logger.info("Workday %s: 0 jobs (URL may be wrong: %s)", 
                       company_name, base_url[:60])
            return []

        # Filter by search terms and location
        matched = []
        search_terms_lower = [t.lower() for t in search_terms]
        for job in all_jobs:
            title = (job.get("title") or "").lower()
            desc = (job.get("description") or "").lower()

            term_match = False
            for term in search_terms_lower:
                words = term.split()
                if all(w in title for w in words):
                    term_match = True
                    break
                if all(w in desc for w in words):
                    term_match = True
                    break
            if not term_match:
                continue

            if loc_filters:
                job_loc = (job.get("location") or "").lower()
                if not any(loc in job_loc for loc in loc_filters) and "remote" not in job_loc:
                    continue

            job["source"] = "ats_discovery"
            job["ats_platform"] = "workday"
            job["company"] = job.get("company") or company_name
            matched.append(job)

        if matched:
            logger.info("Workday %s: %d jobs matched filters", company_name, len(matched))

        return matched
    except Exception as e:
        logger.info("Workday %s FAILED: %s (URL: %s)", 
                   company_name, str(e)[:80], base_url[:60])
        return []
