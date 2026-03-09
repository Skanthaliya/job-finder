# Job Finder — Personal Job Search Aggregator

A production-ready local tool that scrapes jobs from major job boards, discovers hidden jobs from company career pages via Google dorking, detects job language (English/German), and outputs results to Excel. Features a Streamlit web GUI.

## Features

### Phase 1 (Current)
- **Multi-source job scraping**
  - Job boards via [python-jobspy](https://github.com/Bunsly/JobSpy): Indeed, LinkedIn, Google Jobs, Glassdoor, ZipRecruiter
  - Google Dorking: discovers jobs directly on company career pages
  - ATS API scrapers: Greenhouse, Lever, Workday, Personio, Ashby, SmartRecruiters
  - Public APIs: Arbeitnow, Remotive
  - Generic HTML scraper for unknown career pages
- **Language detection** — automatically classifies jobs as English, German, etc.
- **Smart deduplication** — merges duplicate listings, keeps the most complete version
- **Formatted Excel output** — multi-sheet workbook with hyperlinks, color coding, auto-sizing
- **Streamlit GUI** — web-based interface with real-time progress, charts, and interactive data table
- **CLI interface** — full command-line support with argument parsing

### Phase 2 (Planned)
- Google Gemini AI integration
- Job scoring against your resume profile
- AI-generated cover letters
- Resume bullet point tailoring

## Setup

### Prerequisites
- Python 3.11+ (uses `X | None` type syntax)
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
# Basic search
python main.py

# Custom search
python main.py --search "Data Engineer" --location "Munich" --country "Germany"

# Remote jobs only
python main.py --search "Python Developer" --location "Berlin" --remote

# Filter by language
python main.py --search "Software Engineer" --location "Berlin" --language English

# Disable specific sources
python main.py --no-dork --no-arbeitnow

# Enable Remotive (disabled by default)
python main.py --remotive

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
| `--search`, `-s` | "Software Engineer" | Job title or keywords |
| `--location`, `-l` | "Berlin" | City or region |
| `--country`, `-c` | "Germany" | Country |
| `--hours` | 168 (7 days) | Max job age in hours |
| `--results` | 50 | Results per site |
| `--type` | None | fulltime, parttime, contract, internship |
| `--remote` | False | Remote jobs only |
| `--language` | None | English, German, French, Spanish |
| `--no-jobspy` | False | Disable JobSpy |
| `--no-dork` | False | Disable Google Dorking |
| `--no-arbeitnow` | False | Disable Arbeitnow |
| `--remotive` | False | Enable Remotive |
| `--format` | excel | excel or csv |
| `--sites` | indeed linkedin google | JobSpy sites |

## Configuration

Edit `config.py` to customize:

- **Search defaults** — default keywords, location, country
- **Dork templates** — Google dork query patterns
- **ATS patterns** — URL regex for identifying ATS platforms
- **HTTP settings** — timeouts, retries, User-Agent rotation
- **Rate limiting** — delays between Google dork queries

### Profile Setup (Phase 2)

Edit `my_profile.json` with your resume data to prepare for AI features:
- Skills, experience, education
- Preferred keywords and dealbreakers
- Language proficiency

## Project Structure

```
job-finder/
├── config.py                    # All configuration and constants
├── scrapers/
│   ├── jobspy_scraper.py        # python-jobspy wrapper
│   ├── google_dorker.py         # Google dork query engine
│   ├── url_router.py            # URL classifier → ATS scraper dispatcher
│   ├── ats/
│   │   ├── base.py              # Abstract base class for ATS scrapers
│   │   ├── greenhouse.py        # Greenhouse boards API
│   │   ├── lever.py             # Lever postings API
│   │   ├── workday.py           # Workday internal API
│   │   ├── personio.py          # Personio XML/HTML scraper
│   │   ├── ashby.py             # Ashby jobs API
│   │   ├── smartrecruiters.py   # SmartRecruiters API
│   │   └── generic.py           # Generic HTML fallback
│   └── apis/
│       ├── arbeitnow.py         # Arbeitnow.com API
│       └── remotive.py          # Remotive.com API
├── processing/
│   ├── normalizer.py            # Normalize to unified schema
│   ├── language_detector.py     # langdetect wrapper
│   └── deduplicator.py          # Smart deduplication
├── output/
│   ├── excel_writer.py          # Formatted .xlsx output
│   └── csv_writer.py            # CSV fallback
├── ai/                          # Phase 2 stubs
│   ├── scorer.py                # Gemini job scoring
│   ├── cover_letter.py          # Gemini cover letter gen
│   └── resume_tailor.py         # Gemini resume tailoring
├── app.py                       # Streamlit GUI
├── main.py                      # CLI entry point + orchestrator
├── my_profile.json              # User profile template
├── requirements.txt
└── README.md
```

## Architecture

### Data Flow

```
1. User configures search → app.py or main.py
2. Orchestrator runs scrapers in parallel:
   ├── JobSpy → Indeed, LinkedIn, Google Jobs...
   ├── Google Dorker → discovers URLs → URL Router → ATS Scrapers
   ├── Arbeitnow API
   └── Remotive API
3. All results merged → unified schema
4. Normalizer → standardize fields
5. Language Detector → classify each job
6. Language Filter → (if set)
7. Deduplicator → merge duplicates
8. Output → Excel / CSV
```

### Unified Job Schema

Every scraper returns data in the same format:

```python
{
    "source": str,              # "indeed", "linkedin", "google_dork", "arbeitnow"
    "ats_platform": str | None, # "workday", "greenhouse", "lever", etc.
    "title": str,
    "company": str,
    "location": str,
    "country": str | None,
    "date_posted": str | None,  # ISO "YYYY-MM-DD"
    "job_type": str | None,     # "fulltime", "parttime", "contract", "internship"
    "is_remote": bool | None,
    "salary_min": float | None,
    "salary_max": float | None,
    "salary_currency": str | None,
    "salary_interval": str | None,
    "job_url": str,
    "company_url": str | None,
    "description": str | None,
    "language": str | None,     # "English", "German", "unknown"
    # Phase 2 AI fields
    "ai_score": int | None,
    "ai_reasoning": str | None,
    "ai_cover_letter": str | None,
    "ai_resume_bullets": str | None,
}
```

## Known Limitations

- **Rate Limiting**: Google dorking may get rate-limited (HTTP 429). The tool waits 30s and skips. Space out searches.
- **LinkedIn Scraping**: LinkedIn aggressively blocks scrapers. Results may be limited.
- **Workday**: The most complex ATS to scrape. Some companies have non-standard configurations that the scraper can't handle — it falls back to returning the URL with minimal info.
- **JavaScript-rendered Pages**: The generic scraper only works with server-rendered HTML. JS-heavy career pages (React/Angular SPAs) may return minimal data.
- **Accuracy**: Language detection requires sufficient text. Short descriptions may be classified as "unknown".
- **Terms of Service**: Web scraping may violate the ToS of some sites. Use responsibly and for personal use only.

## Troubleshooting

### "python-jobspy not installed"
```bash
pip install python-jobspy
```

### "googlesearch-python not installed"
```bash
pip install googlesearch-python
```

### Rate limited by Google
- Increase `GOOGLE_DORK_DELAY_MIN` and `GOOGLE_DORK_DELAY_MAX` in `config.py`
- Reduce the number of dork templates
- Disable Google dorking with `--no-dork` and use only job board scrapers

### Excel file won't open
- Ensure `openpyxl` is installed: `pip install openpyxl`
- Check the `output/` directory for the generated file

### No results from JobSpy
- Some sites may be temporarily blocking requests
- Try different combinations of sites: `--sites indeed google`
- Broaden search terms or increase `--hours`

### Streamlit won't start
```bash
pip install streamlit
streamlit run app.py --server.port 8501
```

### Encoding issues with German characters
- The tool uses UTF-8 throughout. If Excel shows garbled text, try opening with "UTF-8" encoding explicitly.

## License

Personal use only. Respect the terms of service of all scraped websites.
