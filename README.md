# Job Finder — Personal Job Search Aggregator

A production-ready local tool that scrapes jobs from major job boards, queries 250+ company ATS portals directly, discovers hidden jobs via SerpAPI dorking, detects job language requirements (English/German), and outputs results to Excel. Features a Streamlit web GUI.

## Features

### Phase 1 (Current)
- **Multi-source job scraping**
  - Job boards via [python-jobspy](https://github.com/Bunsly/JobSpy): Indeed, LinkedIn, Google Jobs, Glassdoor, ZipRecruiter
  - ATS Discovery: queries 250+ companies directly via Greenhouse, Lever, Workday, Personio, Ashby, SmartRecruiters APIs
  - SerpAPI Dorking: discovers hidden jobs via Google search API with quota tracking (100/month free tier)
  - Public APIs: Arbeitnow (Germany-focused), Remotive (remote jobs)
  - Auto-growing company registry: new companies discovered from results are saved for future searches
  - Generic HTML scraper fallback for unknown career pages
- **Smart language detection** — 46+ regex patterns detect language REQUIREMENTS (not just text language): English, German, "English (German plus)"
- **Smart deduplication** — merges duplicate listings, keeps the most complete version
- **Formatted Excel output** — multi-sheet workbook with hyperlinks, color coding, auto-sizing
- **Streamlit GUI** — web-based interface with real-time progress, charts, and interactive data table
- **CLI interface** — full command-line support with argument parsing

### Phase 2 (Active)
- **AI Job Scoring** — Gemini scores each job 1-100 against your CV (batch mode, progress bar)
- **AI Cover Letters** — one-click tailored cover letter per job, auto-detects language
- **CV Input** — paste all your CVs in the sidebar text box, or keep a `my_profile.txt` backup file
- Resume bullet point tailoring (coming soon)

## Setup

### Prerequisites
- Python 3.12+ (uses `X | None` type syntax)
- pip

### Installation

```bash
# Navigate to the project directory
cd job-finder

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # macOS/Linux
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Set up API keys
cp .env.example .env
# Edit .env and add your keys:
#   SERPAPI_KEY=...       (optional — free: 100 searches/month at serpapi.com)
#   GEMINI_API_KEY=...    (for AI scoring + cover letters — free at aistudio.google.com/apikey)
```

## Usage

### Streamlit GUI (Recommended)

```bash
cd job-finder
streamlit run app.py
```

This opens a web app at http://localhost:8501 with:
- Sidebar for configuring search parameters
- Checkboxes for enabling/disabling data sources
- Real-time progress updates during search
- Interactive results table with clickable job links
- Charts showing jobs by source and language
- Download buttons for Excel and CSV

### Command Line

```bash
# Basic search (uses 12 default roles, searches all of Germany)
python main.py --scope country

# Custom search
python main.py --search "Data Engineer" --location "Munich" --country "Germany"

# Country-wide search with specific roles
python main.py --search "Product Owner" "Scrum Master" --scope country --country Germany

# Europe-wide search
python main.py --search "Product Manager" --scope europe

# Remote jobs only
python main.py --search "Python Developer" --remote

# Filter by language
python main.py --search "Software Engineer" --scope country --language English

# Disable specific sources (faster search)
python main.py --no-ats --no-arbeitnow

# Enable optional sources
python main.py --remotive --serpapi

# CSV output
python main.py --format csv

# Specify JobSpy sites
python main.py --sites indeed linkedin google

# All options
python main.py --help
```

### CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `--search`, `-s` | 12 default roles | Job titles to search (multiple allowed) |
| `--location`, `-l` | "" (whole country) | City or region |
| `--scope` | "city" | Location scope: city / country / europe |
| `--country`, `-c` | "Germany" | Country |
| `--hours` | 168 (7 days) | Max job age in hours |
| `--results` | 50 | Results per site per term |
| `--type` | None | fulltime, parttime, contract, internship |
| `--remote` | False | Remote jobs only |
| `--language` | None | English, German, French, Spanish |
| `--no-jobspy` | False | Disable JobSpy scraper |
| `--no-ats` | False | Disable ATS Discovery engine |
| `--no-arbeitnow` | False | Disable Arbeitnow API |
| `--remotive` | False | Enable Remotive API |
| `--serpapi` | False | Enable SerpAPI dorking |
| `--format` | excel | excel or csv |
| `--sites` | indeed linkedin google | JobSpy sites to use |

## Configuration

Edit `config.py` to customize:

- **Search defaults** — default keywords (12 roles), location, country
- **ATS patterns** — URL regex for identifying ATS platforms from job URLs
- **SerpAPI dork templates** — Google dork query patterns for SerpAPI
- **HTTP settings** — timeouts (30s), retries (2), User-Agent rotation
- **Location settings** — European countries list, location scope options

### AI Profile Setup

To use AI scoring and cover letter generation, provide your CV text via one of these methods (in priority order):

1. **Sidebar text box** — paste all your CV content directly in the Streamlit sidebar
2. **`my_profile.txt`** — create this file in the project root with all your CVs copy-pasted
3. **`my_profile.json`** — fill in the structured template (auto-flattened to text)

You also need a Gemini API key (free at [aistudio.google.com/apikey](https://aistudio.google.com/apikey)).

## Project Structure

```
job-finder/
├── config.py                    # All configuration and constants
├── main.py                      # CLI entry point + run_search() orchestrator
├── app.py                       # Streamlit web GUI
├── scrapers/
│   ├── jobspy_scraper.py        # python-jobspy wrapper (Indeed, LinkedIn, etc.)
│   ├── ats_discovery.py         # Direct ATS API calls for 250+ companies
│   ├── serpapi_dorker.py        # SerpAPI Google dorking with quota tracking
│   ├── url_router.py            # URL classifier → ATS scraper dispatcher
│   ├── company_registry.py      # Auto-growing company list (JSON on disk)
│   ├── company_list_updater.py  # Downloads company lists from GitHub repos
│   ├── google_dorker.py         # LEGACY — not used (replaced by SerpAPI)
│   ├── ats/
│   │   ├── base.py              # Abstract base class (retry, User-Agent rotation)
│   │   ├── greenhouse.py        # Greenhouse boards API
│   │   ├── lever.py             # Lever postings API
│   │   ├── workday.py           # Workday internal JSON API
│   │   ├── personio.py          # Personio XML feed + HTML fallback
│   │   ├── ashby.py             # Ashby posting API
│   │   ├── smartrecruiters.py   # SmartRecruiters public API
│   │   └── generic.py           # BeautifulSoup fallback for unknown sites
│   └── apis/
│       ├── arbeitnow.py         # Arbeitnow.com API (Germany-focused)
│       └── remotive.py          # Remotive.com API (remote jobs)
├── processing/
│   ├── normalizer.py            # Unified schema normalization, date parsing
│   ├── language_detector.py     # 46+ regex patterns for language requirement detection
│   └── deduplicator.py          # URL + title/company dedup, source merging
├── output/
│   ├── excel_writer.py          # 3-sheet Excel with formatting and hyperlinks
│   └── csv_writer.py            # CSV fallback output
├── ai/                          # Phase 2 — AI scoring + cover letters (active)
│   ├── profile_loader.py        # Loads CV text: sidebar → my_profile.txt → my_profile.json
│   ├── scorer.py                # Gemini job scoring (1-100) with batch support
│   ├── cover_letter.py          # Gemini cover letter generation (auto language)
│   └── resume_tailor.py         # Gemini resume bullet tailoring (STUB)
├── my_profile.json              # Structured profile template (JSON fallback)
├── my_profile.txt               # Plain text CV backup (paste all CVs here)
├── .env.example                 # Template for API keys
├── requirements.txt
├── CONTEXT.md                   # Full project context & AI handoff doc
└── README.md
```

## Architecture

### Data Flow

```
1. User configures search → app.py (GUI) or main.py (CLI)
2. Orchestrator runs scrapers in parallel (4-worker ThreadPoolExecutor):
   ├── JobSpy → Indeed, LinkedIn, Google Jobs (per site, per term)
   ├── ATS Discovery → Greenhouse, Lever, Ashby, SmartRecruiters, Personio, Workday (250+ companies)
   ├── Arbeitnow API (Germany-focused)
   ├── Remotive API (remote jobs, optional)
   └── SerpAPI Dorking (optional) → URL Router → ATS Scrapers
3. Normalize all results → unified schema
4. Detect language requirements (46+ regex patterns)
5. Apply language filter (if set)
6. Apply location filter (blocks US-only remote, keeps EU/India remote)
7. Deduplicate (URL + title/company matching)
8. Auto-learn new companies from job URLs → save to registry
9. Sort by date descending
10. Output → Excel / CSV
```

### Unified Job Schema

Every scraper returns data in the same format:

```python
{
    "source": str,              # "indeed", "linkedin", "ats_discovery", "arbeitnow", "remotive", "google_dork"
    "ats_platform": str | None, # "workday", "greenhouse", "lever", etc.
    "title": str,
    "company": str,
    "location": str,
    "country": str | None,
    "date_posted": str | None,  # ISO "YYYY-MM-DD"
    "job_type": str | None,     # "fulltime", "parttime", "contract", "internship"
    "experience_level": str | None, # "intern", "entry", "junior", "mid", "senior", "lead", etc.
    "is_remote": bool | None,
    "salary_min": float | None,
    "salary_max": float | None,
    "salary_currency": str | None,
    "salary_interval": str | None,
    "job_url": str,
    "company_url": str | None,
    "description": str | None,
    "language": str | None,     # "English", "German", "English (German plus)", "unknown"
    # AI fields (populated by ai/scorer.py)
    "ai_score": int | None,        # 1-100 relevance score
    "ai_reasoning": str | None,    # Score reasoning + pros/cons
    "ai_cover_letter": str | None,
    "ai_resume_bullets": str | None,
}
```

## Known Limitations

- **SerpAPI quota**: Free tier allows 100 searches/month. Quota is tracked in `serpapi_usage.json`. Use `--serpapi` flag to enable (off by default to conserve quota).
- **Workday URLs**: Many configured Workday URLs return 404. The tenant URL format (`{tenant}.wd{N}.myworkdayjobs.com`) is fragile and company-specific.
- **Lever slugs**: ~90% of configured Lever company slugs return 404. Companies may have changed ATS or slugs.
- **Google Jobs via JobSpy**: Google frequently returns HTTP 429 (rate limit). Not critical since other sources provide good coverage.
- **LinkedIn Scraping**: LinkedIn aggressively blocks scrapers. Results may be limited.
- **No date filter for ATS Discovery**: ATS APIs don't support date filtering natively. Old job postings may appear in results.
- **JavaScript-rendered Pages**: The generic scraper only works with server-rendered HTML. JS-heavy career pages (React/Angular SPAs) may return minimal data.
- **Language detection accuracy**: Requires sufficient description text. Short descriptions may be classified as "unknown".
- **Terms of Service**: Web scraping may violate the ToS of some sites. Use responsibly and for personal use only.

## Troubleshooting

### "python-jobspy not installed"
```bash
pip install python-jobspy
```

### SerpAPI not working
- Ensure you have a valid API key: sign up at [serpapi.com](https://serpapi.com)
- Copy `.env.example` to `.env` and add your key: `SERPAPI_KEY=your_key_here`
- Check quota: free tier is 100 searches/month (tracked in `serpapi_usage.json`)
- SerpAPI is off by default — enable with `--serpapi` flag

### No results from ATS Discovery
- ATS Discovery queries 250+ companies. If returning 0 results, check `job_finder.log` for errors.
- Many Workday/Lever URLs are known to 404 — this is expected. Greenhouse, Ashby, and SmartRecruiters are the most reliable.
- Try disabling ATS Discovery with `--no-ats` to isolate the issue.

### No results from JobSpy
- Some sites may be temporarily blocking requests
- Google Jobs frequently returns 429 — this is normal
- Try different combinations of sites: `--sites indeed linkedin`
- Broaden search terms or increase `--hours`

### Excel file won't open
- Ensure `openpyxl` is installed: `pip install openpyxl`
- Check the `output/` directory for the generated file

### Streamlit won't start
```bash
pip install streamlit
streamlit run app.py --server.port 8501
```

### Encoding issues with German characters
- The tool uses UTF-8 throughout. If Excel shows garbled text, try opening with "UTF-8" encoding explicitly.

### Check logs for detailed errors
```bash
cat job_finder.log | grep -i "error\|failed"
```

## License

Personal use only. Respect the terms of service of all scraped websites.
