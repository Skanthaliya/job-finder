# Job Finder — Complete Project Context & AI Handoff

## Repository
- **Repo:** https://github.com/Skanthaliya/job-finder
- **Branch:** `main`
- **Latest commit:** `2fd3e63` (2026-03-13) — "context handoff"
- **Language:** Python 3.12+
- **GUI:** Streamlit
- **Status:** Phase 1 COMPLETE ✅ — Core job search working. Phase 2 (AI) NOT started.

---

## Quick Start

```bash
cd job-finder
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Then fill in your SERPAPI_KEY

# Quick test (small search, fast)
python3 main.py --search "Product Owner" --scope country --country Germany --results 5 --no-ats

# Full search (all sources)
python3 main.py --scope country --country Germany

# GUI
streamlit run app.py
```

Typical runtime: 30-90 seconds depending on sources enabled. ATS Discovery adds ~60s (250+ API calls). A minimal `--no-ats` search completes in ~15s.

---

## User Context

The user (Skanthaliya) is a job seeker in **Germany** with an EU/India work permit.

- **Target roles:** Product Owner, Product Manager, Project Manager, Scrum Master, Business Analyst, Graduate IT
- **Target location:** Germany (whole country), with option for EU-wide search
- **Language preference:** English jobs, or English jobs where "German is a plus"
- **Cannot apply to:** Jobs requiring US/Canada-only remote work
- **CAN apply to:** Remote jobs available in EU or India, or global remote
- **SerpAPI account:** Active, free tier (100 searches/month)
- **FlowCV:** Uses FlowCV for resume design — NO API available
- **Mac user:** macOS, Python 3.12 via Homebrew, uses `source venv/bin/activate`

---

## Project Structure

```
job-finder/
├── config.py                          # All defaults, constants, ATS patterns
├── main.py                            # CLI + orchestrator (run_search function)
├── app.py                             # Streamlit GUI
├── my_profile.json                    # User resume template (for AI Phase 2)
├── requirements.txt                   # python-jobspy, streamlit, langdetect, etc.
├── .env.example                       # Template for required env vars (SERPAPI_KEY, GEMINI_API_KEY)
├── .gitignore                         # venv, output, .env, registry files
├── README.md                          # User-facing documentation
├── CONTEXT.md                         # ← This file — project context & handoff
├── scrapers/
│   ├── jobspy_scraper.py              # python-jobspy wrapper (Indeed, LinkedIn, etc.)
│   ├── ats_discovery.py               # Direct ATS API calls (Greenhouse, Lever, etc.)
│   ├── serpapi_dorker.py              # SerpAPI Google dorking with quota tracking
│   ├── url_router.py                  # Classifies URLs → dispatches to ATS scrapers
│   ├── company_registry.py            # Auto-growing company list (JSON on disk)
│   ├── company_list_updater.py        # Downloads company lists from GitHub repos
│   ├── google_dorker.py               # LEGACY — Google rate-limits this, not used
│   ├── apis/
│   │   ├── arbeitnow.py              # Arbeitnow.com public API
│   │   └── remotive.py               # Remotive.com public API
│   └── ats/
│       ├── base.py                    # Base scraper class (retry, User-Agent rotation)
│       ├── greenhouse.py              # Greenhouse boards API
│       ├── lever.py                   # Lever postings API
│       ├── workday.py                 # Workday internal JSON API
│       ├── personio.py                # Personio XML feed + HTML fallback
│       ├── ashby.py                   # Ashby posting API
│       ├── smartrecruiters.py         # SmartRecruiters public API
│       └── generic.py                 # BeautifulSoup fallback for unknown sites
├── processing/
│   ├── language_detector.py           # Detects LANGUAGE REQUIREMENT (not just text lang)
│   ├── deduplicator.py               # URL + title/company dedup
│   └── normalizer.py                 # Unified schema, date normalization
├── output/
│   ├── excel_writer.py               # 3-sheet Excel (summary, full, AI placeholder)
│   └── csv_writer.py                 # CSV fallback
└── ai/                                # Phase 2 — ALL STUBS (NotImplementedError)
    ├── scorer.py                      # Gemini job scoring (0-100)
    ├── cover_letter.py                # Gemini cover letter generation
    └── resume_tailor.py               # Gemini resume bullet tailoring
```

---

## Phase 1 — COMPLETE — What Works

> **Note on phase numbering:** Git commit messages reference "phase 2" and "phase 3" for scraper feature additions (ATS discovery, company registry, etc.). In this document, "Phase 1" means ALL scraping/processing work (complete), and "Phase 2" means AI features (not started). The git history phases and this document's phases are different numbering schemes.

### Data Sources (all working)

| Source | Method | Status | Notes |
|--------|--------|--------|-------|
| **Indeed** | JobSpy library, per-site per-term | ✅ Working | Best scraper, no rate limits |
| **LinkedIn** | JobSpy library | ✅ Working | Rate-limits ~10 pages |
| **Google Jobs** | JobSpy library | ⚠️ Often 429'd | Google blocks from same IP |
| **Glassdoor** | JobSpy library | ✅ Working | Optional, off by default |
| **Arbeitnow** | Direct REST API | ✅ Working | Germany-focused, has tags |
| **Remotive** | Direct REST API | ✅ Working | Remote-only jobs |
| **Greenhouse** | Direct boards API, ~80 companies | ✅ Working | No auth needed |
| **Lever** | Direct postings API, ~40 companies | ⚠️ Many 404s | Many slugs are wrong |
| **Ashby** | Direct posting API, ~30 companies | ✅ Working | No auth needed |
| **SmartRecruiters** | Direct postings API, ~20 companies | ✅ Working | Fixed URL construction |
| **Personio** | XML feed + HTML fallback, ~40 companies | ✅ Working | German startups |
| **Workday** | Internal JSON API, ~30 company URLs | ⚠️ Untested | URLs may be wrong |
| **SerpAPI** | Google dorking via paid API (free tier) | ✅ Working | 100/month, quota tracked |

### Key Features Working

- **Multi-role search:** 12 default roles searched simultaneously (configurable)
- **Location scope:** City / Country / Europe dropdown
- **Smart language detection:** 46+ regex patterns detect German REQUIRED vs German IS A PLUS vs English-only
- **Location filter:** Blocks "Remote in United States", keeps "Remote" and "Remote - EU"
- **ATS Discovery:** Queries 250+ companies directly across 6 ATS platforms
- **Auto-growing company list:** New companies discovered from results saved to `company_registry.json`
- **Company list updater:** Downloads from GitHub repos weekly
- **SerpAPI dorking:** Batches roles with OR to conserve quota, routes URLs to ATS scrapers
- **URL junk filter:** Blocks Facebook, landing pages, search result pages
- **Deduplication:** URL + title/company matching
- **Excel output:** 3 sheets with color-coding, hyperlinks, auto-width
- **Streamlit GUI:** Full sidebar config, progress bar, charts, data table, download buttons
- **.env support:** API keys via `python-dotenv`
- **Parallel scraping:** 4-worker ThreadPoolExecutor for concurrent API calls

### Processing Pipeline (in order)

1. Run scrapers in parallel (JobSpy + Arbeitnow + Remotive + ATS Discovery + SerpAPI)
2. Normalize all jobs to unified schema
3. Detect language requirements (English / German / English (German plus) / unknown)
4. Apply language filter
5. Apply location filter (blocks US-only remote, keeps EU/India remote)
6. Deduplicate
7. Auto-learn new companies from job URLs → save to registry
8. Sort by date descending
9. Write to Excel/CSV

---

## Phase 2 — NOT STARTED — AI Features

All files in `ai/` are **stubs** that raise `NotImplementedError`.

### Interfaces Already Defined

```python
# ai/scorer.py
score_job(job: dict, profile: dict) -> dict       # {score: 0-100, reasoning, pros, cons}
score_jobs_batch(jobs, profile, top_n=50) -> list  # Score all, return top N

# ai/cover_letter.py
generate_cover_letter(job, profile, language="English") -> str  # 3-4 paragraphs, <400 words

# ai/resume_tailor.py
generate_tailored_bullets(job, profile) -> str     # Rewrite bullets to match job keywords
```

### What Needs To Be Built

**1. `ai/scorer.py` — Job Scoring with Gemini**
- Use `google-generativeai` package with model `gemini-2.0-flash`
- Read `GEMINI_API_KEY` from env var or `.env`
- Rate limit: 0.5s delay between API calls
- Parse JSON from Gemini response (handle markdown-wrapped JSON)

**2. `ai/cover_letter.py` — Cover Letter Generation**
- Language parameter determines output language (English/German)
- 3-4 paragraphs, professional tone, under 400 words
- Must NOT fabricate experience — use only what's in profile

**3. `ai/resume_tailor.py` — Resume Bullet Tailoring**
- Rewrite resume bullets to match job keywords
- Truthful only — no fabrication

**4. `app.py` — AI Section in GUI**
- Replace Phase 2 placeholder with actual UI
- Text input for GEMINI_API_KEY (masked)
- "Score Jobs" button → progress bar → sorted results with ai_score
- For top-10 jobs: expandable sections with score, reasoning, cover letter button, resume button
- Download updated Excel with AI columns filled

**5. `output/excel_writer.py` — AI Results Sheet**
- When AI data present, populate Sheet 3 with scores, cover letters
- Conditional formatting: green >70, yellow >40, red ≤40

**6. `my_profile.json` — User fills in their real data**
- Template exists but needs user's actual resume data

---

## Unified Job Schema

Every job in the pipeline uses this exact schema:

```python
{
    "source": str,              # "indeed", "linkedin", "ats_discovery", "arbeitnow", "remotive", "google_dork"
    "ats_platform": str | None, # "workday", "greenhouse", "lever", "personio", "ashby", "smartrecruiters"
    "title": str,
    "company": str,
    "location": str,
    "country": str | None,
    "date_posted": str | None,  # ISO format "2026-03-09"
    "job_type": str | None,     # "fulltime", "parttime", "contract", "internship"
    "is_remote": bool | None,
    "salary_min": float | None,
    "salary_max": float | None,
    "salary_currency": str | None,
    "salary_interval": str | None,
    "job_url": str,             # REQUIRED — direct link to job posting
    "company_url": str | None,
    "description": str | None,  # Full job description text
    "language": str | None,     # "English", "German", "English (German plus)", "unknown"
    "ai_score": int | None,     # Phase 2
    "ai_reasoning": str | None, # Phase 2
    "ai_cover_letter": str | None, # Phase 2
    "ai_resume_bullets": str | None, # Phase 2
}
```

---

## Config Defaults (config.py)

```python
DEFAULT_SEARCH_TERMS = [
    "Product Owner", "Junior Product Owner",
    "Product Manager", "Junior Product Manager",
    "Project Manager", "Junior Project Manager",
    "Scrum Master", "Junior Scrum Master",
    "Business Analyst", "IT Business Analyst",
    "Graduate IT", "Business Informatics",
]
DEFAULT_LOCATION = ""          # Empty = whole country
DEFAULT_LOCATION_SCOPE = "Country"
DEFAULT_COUNTRY = "Germany"
DEFAULT_HOURS_OLD = 168        # 7 days
DEFAULT_RESULTS_PER_SITE = 50
LANGUAGE_FILTER_OPTIONS = ["All", "English", "English (German plus)", "German", "French", "Spanish"]
```

### HTTP Settings
- Timeout: 30 seconds
- Max retries: 2
- User-Agent rotation: 3 browser agents

### ATS Platform Detection Patterns (config.py)
The system auto-detects ATS platforms from job URLs using regex patterns for: Workday, Greenhouse, Lever, Personio, Ashby, SmartRecruiters, iCIMS, and Taleo.

### SerpAPI Dorking
- 3-tier dork templates: Major ATS, More ATS, Wild discovery
- Language-specific dorks for English & German jobs
- Quota tracked in `serpapi_usage.json`
- Roles batched with OR to conserve searches

---

## Architecture Decisions Made

1. **Google dorking abandoned** — `googlesearch-python` gets 100% rate-limited by Google. Replaced with SerpAPI (paid but free tier) + direct ATS API calls.

2. **Per-site-per-term JobSpy** — JobSpy runs each search term on each site individually (not combined) because the library only accepts one term at a time. 6 terms × 3 sites = 18 API calls.

3. **Language = requirement, not text language** — `langdetect` only detects what language text is written in. Our `language_detector.py` uses 46+ regex patterns to detect what language the JOB REQUIRES (e.g., "German is a plus" in English text → "English (German plus)").

4. **Remote filter allows EU/India** — "Remote in United States" is blocked. "Remote" with no country, or "Remote - EU/Germany/India" is kept. This matches the user's work permit situation.

5. **ATS Discovery over dorking** — Instead of searching Google for ATS URLs, we directly call Greenhouse/Lever/Ashby/SmartRecruiters/Personio/Workday APIs with curated lists of 250+ companies. Faster, more reliable, never rate-limited.

6. **Auto-growing company list** — Every job URL is checked for ATS patterns. New companies saved to `company_registry.json` for future searches. SerpAPI discoveries also auto-save.

7. **No auto-apply** — Investigated and rejected. Most application forms have CAPTCHAs, custom questions, anti-bot protection. Risk of account bans. Plan: build "application prep" (AI generates cover letter + resume bullets, user applies manually).

8. **No FlowCV API** — FlowCV has no API. Plan for AI phase: generate `.docx` resume files directly using `python-docx`, which user can upload to FlowCV or use as-is.

9. **Parallel execution with error isolation** — 4-worker ThreadPoolExecutor runs scrapers concurrently. Each scraper runs inside a `_run_*_safe()` wrapper that catches all exceptions, so one failing scraper never crashes the pipeline. Each future has a 5-minute timeout (`future.result(timeout=300)`).

10. **Progressive language detection** — Detection order: explicit "no German" override → German optional patterns → German required patterns → English working language patterns → langdetect text language → title patterns. This prevents false positives.

---

## What NOT to Change (Fragile Areas)

1. **JobSpy per-site-per-term pattern** — JobSpy only accepts one search term at a time. The nested `for site in sites: for term in search_terms:` loop in `main.py` is intentional. Do not try to batch terms.

2. **Language detection order** in `language_detector.py` — The cascade (explicit "no German" → German optional → German required → English working language → langdetect → title patterns) prevents false positives. Reordering will break classification accuracy.

3. **Workday URL format** — Workday URLs follow `{tenant}.wd{N}.myworkdayjobs.com/en-US/{path}` exactly. The `wd{N}` number is tenant-specific and cannot be guessed. Wrong numbers = 404.

4. **Safe wrapper pattern** — Every scraper runs inside a `_run_*_safe()` wrapper in `main.py` that catches all exceptions. This prevents one failing scraper from crashing the entire pipeline. Each scraper has a 5-minute timeout (`future.result(timeout=300)`).

5. **Location filter logic** — The remote job filter in `main.py` (step 4.5) has carefully ordered checks: blocked countries first, then global remote keywords, then allowed countries, then benefit-of-doubt fallback. Reordering changes which jobs are kept.

---

## Known Issues & Tech Debt

| Issue | Severity | Details |
|-------|----------|---------|
| **Workday URLs mostly wrong** | Medium | ~30 URLs configured but many return 404. Check logs for `Workday X: 0 jobs (URL may be wrong)` |
| **Lever slugs ~90% wrong** | Medium | Most Lever companies return 404. May have moved ATS or changed slugs |
| **Google Jobs via JobSpy gets 429'd** | Low | Google blocks automated requests. Not critical — other sources cover it |
| **`google_dorker.py` is dead code** | Low | Replaced by `serpapi_dorker.py`. File kept but never called. Can delete |
| **SerpAPI quota not visible in CLI** | Low | GUI shows usage, CLI doesn't |
| **No job age filter for ATS Discovery** | Medium | ATS APIs don't support date filtering. Old jobs appear. Needs post-processing date filter |
| **Company list GitHub URLs may 404** | Low | `company_list_updater.py` tries specific GitHub URLs that may not exist. Fails silently |

---

## How to Run

```bash
# Setup
cd job-finder
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set API keys
echo 'SERPAPI_KEY=your_key' > .env
echo 'GEMINI_API_KEY=your_key' >> .env    # Phase 2

# CLI
python3 main.py --search "Product Owner" "Scrum Master" --scope country --country Germany --results 10

# GUI
streamlit run app.py
```

### CLI Arguments
| Flag | Default | Description |
|------|---------|-------------|
| `--search` | config defaults | Space-separated search terms |
| `--location` | "" | City name (empty = whole country) |
| `--scope` | "city" | city / country / europe |
| `--country` | "Germany" | Target country |
| `--hours` | 168 | Max job age in hours |
| `--results` | 50 | Results per site per term |
| `--type` | None | fulltime / parttime / contract / internship |
| `--remote` | False | Remote-only flag |
| `--language` | "All" | Language filter |
| `--no-jobspy` | False | Disable JobSpy scraper |
| `--no-ats` | False | Disable ATS Discovery engine |
| `--no-arbeitnow` | False | Disable Arbeitnow API |
| `--remotive` | False | Enable Remotive API (off by default) |
| `--serpapi` | False | Enable SerpAPI dorking (off by default) |
| `--format` | "excel" | Output format: excel / csv |
| `--sites` | indeed linkedin google | JobSpy sites to use |

---

## Testing / Validation

To verify the tool works after changes:

```bash
# 1. Quick smoke test (no ATS, no SerpAPI — fastest)
python3 main.py --search "Product Owner" --scope country --country Germany --results 5 --no-ats

# 2. Check the log file for errors
cat job_finder.log | grep -i "error\|failed\|exception"

# 3. Verify output was created
ls -la output/jobs_*.xlsx

# 4. Full test with ATS Discovery
python3 main.py --search "Product Owner" --scope country --country Germany --results 10
```

**Expected behavior:**
- JobSpy should return 10-50+ jobs per site/term combination
- Arbeitnow should return 20-100+ jobs (Germany-focused)
- ATS Discovery should return 50-200+ jobs across Greenhouse/Ashby/SmartRecruiters (Lever/Workday may return 0 due to known URL issues)
- Deduplication typically removes 10-30% of raw results
- Output Excel has 3 sheets: Summary, Full Data, AI Results (placeholder)

**Common failure modes:**
- `JobSpy: google/... failed: 429` — Google rate-limiting, expected and harmless
- `Workday X: 0 jobs` — Known issue, URL may be wrong
- `Lever X: 404` — Known issue, slug may be wrong

---

## File-by-File Reference

| File | Purpose | Active? |
|------|---------|---------|
| `config.py` | All constants, defaults, ATS patterns, HTTP settings | Yes |
| `main.py` | CLI entry point + `run_search()` orchestrator | Yes |
| `app.py` | Streamlit web GUI | Yes |
| `my_profile.json` | User resume template for AI Phase 2 | Placeholder |
| `scrapers/jobspy_scraper.py` | python-jobspy wrapper, `_map_jobspy_row()` helper | Yes |
| `scrapers/ats_discovery.py` | Direct ATS API calls for 250+ companies | Yes |
| `scrapers/serpapi_dorker.py` | SerpAPI Google dorking with quota tracking | Yes |
| `scrapers/url_router.py` | Classifies URLs by ATS pattern, dispatches to scrapers | Yes |
| `scrapers/company_registry.py` | Auto-growing JSON company list on disk | Yes |
| `scrapers/company_list_updater.py` | Downloads company lists from GitHub repos | Yes |
| `scrapers/google_dorker.py` | Legacy Google dorking — DEAD CODE, never called | No |
| `scrapers/apis/arbeitnow.py` | Arbeitnow.com REST API scraper | Yes |
| `scrapers/apis/remotive.py` | Remotive.com REST API scraper | Yes |
| `scrapers/ats/base.py` | Abstract base class (retry, User-Agent rotation) | Yes |
| `scrapers/ats/greenhouse.py` | Greenhouse boards API scraper | Yes |
| `scrapers/ats/lever.py` | Lever postings API scraper | Yes |
| `scrapers/ats/workday.py` | Workday internal JSON API scraper | Yes |
| `scrapers/ats/personio.py` | Personio XML feed + HTML fallback scraper | Yes |
| `scrapers/ats/ashby.py` | Ashby posting API scraper | Yes |
| `scrapers/ats/smartrecruiters.py` | SmartRecruiters public API scraper | Yes |
| `scrapers/ats/generic.py` | BeautifulSoup fallback for unknown career pages | Yes |
| `processing/normalizer.py` | Maps all jobs to unified schema, normalizes dates | Yes |
| `processing/language_detector.py` | 46+ regex patterns for language requirement detection | Yes |
| `processing/deduplicator.py` | URL + title/company deduplication, source merging | Yes |
| `output/excel_writer.py` | 3-sheet Excel with formatting, hyperlinks, auto-width | Yes |
| `output/csv_writer.py` | CSV fallback output | Yes |
| `ai/scorer.py` | Gemini job scoring — STUB (NotImplementedError) | No |
| `ai/cover_letter.py` | Gemini cover letter generation — STUB | No |
| `ai/resume_tailor.py` | Gemini resume bullet tailoring — STUB | No |

---

## Commit History

| Date | Commit | What Changed |
|------|--------|-------------|
| Mar 9 | `ce5726b` | Initial commit — full project structure, all scrapers |
| Mar 9 | `d3b8cbd` | Streamlit session_state crash fix |
| Mar 9 | `6301a51` | Small fix |
| Mar 9 | `ae28356` | Phase 2 — multi-role, location scope, ATS discovery, SerpAPI, company registry |
| Mar 9 | `d29a4cd` | Phase 3 — company_list_updater, URL router auto-save, Personio added |
| Mar 11 | `dc59556` | Workday ATS, smart language detection, 12 default roles, .env support |
| Mar 11 | `08cff3b` | Fix location filter, SerpAPI scope, broken SmartRecruiters URLs, date parsing, remote filter |
| Mar 11 | `b0ded1d` | Improve German language detection patterns (German Speaker, native-level German, etc.) |
| Mar 13 | `2fd3e63` | Context handoff — added CONTEXT.md, .env.example |

---

## Recommended Next Steps (Priority Order)

### Priority 1: Verify Workday URLs
- Run a search and check logs for `Workday X: 0 jobs` vs `Workday X: N total jobs`
- Fix incorrect URLs in `ats_discovery.py` `WORKDAY_CAREER_URLS` dict
- Remove companies that consistently return 0

### Priority 2: Clean Up Lever Company List
- Most Lever slugs return 404
- Either find correct slugs or remove dead entries
- SerpAPI will discover real Lever companies over time anyway

### Priority 3: Build AI Phase 2
- Implement `ai/scorer.py` with Gemini API
- Implement `ai/cover_letter.py`
- Implement `ai/resume_tailor.py`
- Add AI section to `app.py` GUI
- User needs to fill `my_profile.json` with real resume data

### Priority 4: Application Prep System
- Generate `.docx` cover letters (not FlowCV — no API)
- Select best resume from pre-made versions based on job title
- Open job URL in browser for user to apply manually
- Track applied/skipped status per job

### Priority 5: Enhancements
- Delete dead `google_dorker.py`
- Add date filter for ATS Discovery results (post-processing)
- Add more Greenhouse/Ashby companies (these platforms have correct slugs)
- Consider adding StepStone.de, BerlinStartupJobs, EnglishJobs.de scrapers
- Job history tracking (SQLite) to avoid showing already-seen jobs
- Email/notification for daily new jobs

---

## Dependencies (requirements.txt)

| Package | Version | Purpose |
|---------|---------|---------|
| `python-jobspy` | ≥1.1.75 | Indeed, LinkedIn, Google Jobs, Glassdoor scraping |
| `openpyxl` | ≥3.1.0 | Excel file generation |
| `langdetect` | ≥1.0.9 | Text language detection |
| `streamlit` | ≥1.30.0 | Web GUI |
| `pandas` | ≥2.0.0 | Data manipulation |
| `beautifulsoup4` | ≥4.12.0 | HTML parsing for ATS scrapers |
| `requests` | ≥2.31.0 | HTTP client |
| `lxml` | ≥5.0.0 | XML parsing (Personio feeds) |
| `python-dotenv` | ≥1.0.0 | .env file support |
| `google-generativeai` | ≥0.5.0 | Gemini AI (Phase 2) |

---

*This document is the complete handoff. Any AI agent reading this knows: every file and what it does, what's working vs. broken, all architecture decisions and why, exactly what to build next, and the user's personal context (visa, location, roles).*
