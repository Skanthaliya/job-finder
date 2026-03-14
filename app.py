"""
app.py — Streamlit GUI for the Job Finder tool.

Provides a web-based interface for configuring and running job searches,
viewing results, and downloading output files.

Run: streamlit run app.py
"""

import os
import sys
import logging
import time
from datetime import datetime

import streamlit as st
import pandas as pd
import bleach

# Ensure the project root is in the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    DEFAULT_SEARCH_TERMS,
    DEFAULT_LOCATION,
    DEFAULT_LOCATION_SCOPE,
    COUNTRIES,
    EUROPEAN_COUNTRIES,
    LOCATION_SCOPE_OPTIONS,
    TIME_FILTER_OPTIONS,
    JOB_TYPE_OPTIONS,
    LANGUAGE_FILTER_OPTIONS,
    JOBSPY_SITES,
    COUNTRY_JOBSPY_SITES,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_MODEL_OPTIONS,
)

logger = logging.getLogger(__name__)

_SAFE_HTML_TAGS = [
    "p", "br", "b", "i", "strong", "em", "ul", "ol", "li", "a",
    "h1", "h2", "h3", "h4", "h5", "span", "div", "table", "tr", "td", "th",
    "thead", "tbody", "pre", "code", "blockquote", "hr", "dl", "dt", "dd",
]
_SAFE_HTML_ATTRS = {
    "a": ["href", "target", "rel"],
    "div": ["style"],
    "span": ["style"],
    "td": ["colspan", "rowspan"],
    "th": ["colspan", "rowspan"],
}

# =============================================================================
# Page Configuration
# =============================================================================
st.set_page_config(
    page_title="Job Finder",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =============================================================================
# Custom CSS
# =============================================================================
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.1rem;
        opacity: 0.7;
        margin-bottom: 2rem;
    }
    .stButton > button[kind="primary"] {
        width: 100%;
        font-size: 1.2rem;
        padding: 0.75rem;
    }
    div[data-testid="stExpander"] details summary p {
        font-size: 1rem;
    }
    .bookmark-btn { cursor: pointer; font-size: 1.2rem; }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# Session State Initialization
# =============================================================================
if "search_results" not in st.session_state:
    st.session_state.search_results = None
if "output_filepath" not in st.session_state:
    st.session_state.output_filepath = None
if "search_running" not in st.session_state:
    st.session_state.search_running = False
if "progress_messages" not in st.session_state:
    st.session_state.progress_messages = []
if "ai_scores_done" not in st.session_state:
    st.session_state.ai_scores_done = False
if "cover_letters" not in st.session_state:
    st.session_state.cover_letters = {}
if "resume_bullets" not in st.session_state:
    st.session_state.resume_bullets = {}
if "bookmarked_jobs" not in st.session_state:
    st.session_state.bookmarked_jobs = set()
if "job_page" not in st.session_state:
    st.session_state.job_page = 0

JOBS_PER_PAGE = 25


# =============================================================================
# Sidebar — Search Settings
# =============================================================================
with st.sidebar:
    st.markdown("## ⚙️ Search Settings")

    # Multi-Role Search
    st.markdown("### 🔑 Job Titles / Keywords")
    st.caption("Add multiple roles — one per line")
    search_terms_text = st.text_area(
        "Job Titles",
        value="\n".join(DEFAULT_SEARCH_TERMS),
        height=200,  # Increased from 120 to fit more roles
        label_visibility="collapsed",
    )
    search_terms = [t.strip() for t in search_terms_text.strip().split("\n") if t.strip()]

    st.divider()

    # Location Scope
    st.subheader("📍 Location")
    default_scope_index = LOCATION_SCOPE_OPTIONS.index(DEFAULT_LOCATION_SCOPE) if DEFAULT_LOCATION_SCOPE in LOCATION_SCOPE_OPTIONS else 0

    location_scope = st.selectbox(
        "Search Scope",
        options=LOCATION_SCOPE_OPTIONS,
        index=default_scope_index,
        help="City: specific city. Country: entire country. Europe: all European countries.",
    )

    if location_scope == "City":
        location = st.text_input("City", value=DEFAULT_LOCATION)
        country = st.selectbox("🌍 Country", options=COUNTRIES, index=0)
        search_locations = None
    elif location_scope == "Country":
        country = st.selectbox("🌍 Country", options=COUNTRIES, index=0)
        location = ""  # Empty = whole country
        search_locations = [country]
    else:  # Europe
        country = "Europe"
        location = ""
        search_locations = EUROPEAN_COUNTRIES
        st.info(f"Searching across {len(EUROPEAN_COUNTRIES)} European countries")

    st.divider()

    # Data Sources
    st.markdown("### 📡 Data Sources")

    st.markdown("**Job Boards (via JobSpy)**")
    col1, col2 = st.columns(2)
    with col1:
        use_indeed = st.checkbox("Indeed", value=True)
        use_linkedin = st.checkbox("LinkedIn", value=True)
        use_google_jobs = st.checkbox(
            "Google Jobs", value=False,
            help="⚠️ Unreliable — often returns 0 results due to blocking.",
        )
    with col2:
        use_glassdoor = st.checkbox(
            "Glassdoor", value=False,
            help="⚠️ Unreliable — frequently returns 403 errors.",
        )
        use_ziprecruiter = st.checkbox(
            "ZipRecruiter", value=False,
            help="⚠️ Unreliable — blocked by Cloudflare WAF (429/403).",
        )
        use_naukri = st.checkbox("Naukri (India)", value=False)

    st.markdown("**ATS Discovery (Company Career Pages)**")
    enable_ats_discovery = st.checkbox(
        "Enable ATS Discovery",
        value=True,
        help="Directly queries 120+ company career pages on Greenhouse, Lever, Ashby, "
             "SmartRecruiters. Finds jobs not listed on job boards.",
    )

    st.markdown("**Direct APIs**")
    col1, col2 = st.columns(2)
    with col1:
        use_arbeitnow = st.checkbox("Arbeitnow", value=True)
        use_foundit = st.checkbox("Foundit (India)", value=False)
    with col2:
        use_remotive = st.checkbox("Remotive", value=False)
        use_instahyre = st.checkbox("Instahyre (India)", value=False)

    st.markdown("**Career Page Crawler**")
    enable_career_crawler = st.checkbox(
        "Enable Career Crawler",
        value=False,
        help="Discovers hidden jobs by crawling company career pages found in results. "
             "Detects ATS platforms and scrapes additional listings not on job boards.",
    )

    st.markdown("**SerpAPI Dorking (Optional)**")
    enable_serpapi = st.checkbox(
        "Enable SerpAPI",
        value=False,
        help="Uses SerpAPI to run Google dork queries. Free tier: 100 searches/month. "
             "Sign up at serpapi.com.",
    )
    serpapi_key = ""
    if enable_serpapi:
        serpapi_key = st.text_input(
            "SerpAPI Key",
            type="password",
            help="Enter your SerpAPI key. Sign up free at serpapi.com",
        )
        try:
            from scrapers.serpapi_dorker import get_monthly_usage
            usage = get_monthly_usage()
            st.caption(f"Monthly usage: {usage}/100 queries")
        except Exception as e:
            logger.debug("Failed to load SerpAPI usage: %s", e)

    st.divider()

    # Company Database
    st.markdown("### 📦 Company Database")
    try:
        from scrapers.company_registry import load_registry
        registry = load_registry()
        total_companies = len(registry.get("companies", {}))
        st.caption(f"Companies in database: {total_companies}")

        if st.button("🔄 Update Company Lists", help="Download latest company lists from GitHub"):
            with st.spinner("Downloading company lists..."):
                from scrapers.company_list_updater import update_company_lists
                new_count = update_company_lists(force=True)
                if new_count > 0:
                    st.success(f"Added {new_count} new companies!")
                else:
                    st.info("Company lists are up to date.")
                st.rerun()
    except Exception as e:
        st.caption(f"Company database: error loading ({e})")

    st.divider()

    # Filters
    st.markdown("### 🔧 Filters")

    time_filter = st.selectbox(
        "⏰ Time Filter",
        options=list(TIME_FILTER_OPTIONS.keys()),
        index=2,  # "Last 7 days"
    )
    hours_old = TIME_FILTER_OPTIONS[time_filter]

    results_per_site = st.slider("📊 Results per site", min_value=5, max_value=100, value=30, step=5)

    job_type = st.selectbox("💼 Job Type", options=JOB_TYPE_OPTIONS, index=0)
    if job_type == "Any":
        job_type = None

    is_remote = st.checkbox("🏠 Remote Only", value=False)

    language_filter = st.selectbox("🗣️ Language Filter", options=LANGUAGE_FILTER_OPTIONS, index=0)
    if language_filter == "All":
        language_filter = None

    st.divider()

    # AI Features
    st.markdown("### 🤖 AI Features (Gemini)")

    gemini_api_key = st.text_input(
        "Gemini API Key",
        value=GEMINI_API_KEY,
        type="password",
        help="Get a free key at https://aistudio.google.com/apikey",
    )

    selected_gemini_model = st.selectbox(
        "AI Model",
        options=GEMINI_MODEL_OPTIONS,
        index=0,
        help="2.5-flash: better reasoning, slightly higher cost. 2.0-flash: faster, cheaper.",
    )

    st.markdown("**Your CV / Profile**")
    st.caption("Paste your CV text below. If empty, falls back to `my_profile.txt` → `my_profile.json`.")
    cv_text_input = st.text_area(
        "CV Text",
        height=150,
        placeholder="Paste your full CV / resume text here...",
        label_visibility="collapsed",
    )


# =============================================================================
# Build jobspy_sites list
# =============================================================================
jobspy_sites = []
if use_indeed:
    jobspy_sites.append("indeed")
if use_linkedin:
    jobspy_sites.append("linkedin")
if use_google_jobs:
    jobspy_sites.append("google")
if use_glassdoor:
    jobspy_sites.append("glassdoor")
if use_ziprecruiter:
    jobspy_sites.append("zip_recruiter")
if use_naukri:
    jobspy_sites.append("naukri")

enable_jobspy = len(jobspy_sites) > 0


# =============================================================================
# Main Area
# =============================================================================
st.markdown('<div class="main-header">🔍 Job Finder</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">Aggregate jobs from multiple sources — job boards, '
    'company career pages, and public APIs.</div>',
    unsafe_allow_html=True,
)

# Search Button
col_btn, col_info = st.columns([2, 3])
with col_btn:
    search_clicked = st.button("🚀 Search Jobs", type="primary", use_container_width=True)

with col_info:
    active_sources = []
    if enable_jobspy:
        active_sources.append(f"JobSpy ({', '.join(jobspy_sites)})")
    if enable_ats_discovery:
        active_sources.append("ATS Discovery")
    if use_arbeitnow:
        active_sources.append("Arbeitnow")
    if use_remotive:
        active_sources.append("Remotive")
    if use_foundit:
        active_sources.append("Foundit")
    if use_instahyre:
        active_sources.append("Instahyre")
    if enable_career_crawler:
        active_sources.append("Career Crawler")
    if enable_serpapi and serpapi_key:
        active_sources.append("SerpAPI")
    st.caption(f"Active sources: {' | '.join(active_sources)}")
    if search_terms:
        st.caption(f"Roles: {', '.join(search_terms[:4])}{'...' if len(search_terms) > 4 else ''}")


# =============================================================================
# Run Search
# =============================================================================
if search_clicked:
    st.session_state.search_results = None
    st.session_state.output_filepath = None
    st.session_state.progress_messages = []
    st.session_state.ai_scores_done = False
    st.session_state.cover_letters = {}
    st.session_state.resume_bullets = {}
    st.session_state.bookmarked_jobs = set()
    st.session_state.job_page = 0

    # Set up logging for Streamlit
    from main import setup_logging, run_search
    setup_logging()

    progress_container = st.container()
    progress_bar = st.progress(0, text="Initializing search...")
    status_area = st.empty()

    step_count = [0]
    total_steps = sum([enable_jobspy, enable_ats_discovery, use_arbeitnow, use_remotive, use_foundit, use_instahyre, enable_career_crawler, enable_serpapi]) + 4
    progress_log = []  # Thread-safe regular list instead of session_state

    def streamlit_progress(msg: str) -> None:
        """Update progress in the Streamlit UI (thread-safe)."""
        try:
            progress_log.append(msg)
            step_count[0] += 0.5
            progress_pct = min(step_count[0] / (total_steps * 3), 0.98)
            progress_bar.progress(progress_pct, text=msg[:100])
        except Exception as e:
            logger.debug("Progress update failed (thread-safe): %s", e)

    try:
        with st.spinner("Searching for jobs..."):
            jobs, filepath = run_search(
                search_terms=search_terms,
                location=location,
                search_locations=search_locations,
                country=country,
                hours_old=hours_old,
                results_per_site=results_per_site,
                job_type=job_type,
                is_remote=is_remote,
                language_filter=language_filter,
                enable_jobspy=enable_jobspy,
                jobspy_sites=jobspy_sites if enable_jobspy else None,
                enable_ats_discovery=enable_ats_discovery,
                enable_arbeitnow=use_arbeitnow,
                enable_remotive=use_remotive,
                enable_foundit=use_foundit,
                enable_instahyre=use_instahyre,
                enable_career_crawler=enable_career_crawler,
                enable_serpapi=enable_serpapi and bool(serpapi_key),
                serpapi_key=serpapi_key,
                output_format="excel",
                progress_callback=streamlit_progress,
            )

        st.session_state.search_results = jobs
        st.session_state.output_filepath = filepath
        progress_bar.progress(1.0, text="Search complete!")

    except Exception as e:
        st.error(f"Search failed: {e}")
        logger.error("Search failed: %s", e, exc_info=True)

    # Show progress log
    with st.expander("📋 Search Log", expanded=False):
        for msg in progress_log:
            st.text(msg)


# =============================================================================
# Display Results
# =============================================================================
if st.session_state.search_results is not None:
    jobs = st.session_state.search_results
    filepath = st.session_state.output_filepath

    if not jobs:
        st.warning("No jobs found. Try broadening your search criteria.")
    else:
        st.success(f"Found **{len(jobs)}** jobs!")

        # --- Load AI profile early so it's available in expanders ---
        from ai.profile_loader import load_profile
        profile_text = load_profile(cv_text_input)
        gemini_model = None
        active_model_name = selected_gemini_model if selected_gemini_model else GEMINI_MODEL
        if gemini_api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=gemini_api_key)
                gemini_model = genai.GenerativeModel(active_model_name)
            except Exception as e:
                logger.warning("Failed to initialize Gemini: %s", e)

        # --- Metrics Row ---
        col1, col2, col3, col4 = st.columns(4)

        # Count by source
        source_counts = {}
        for j in jobs:
            src = j.get("source", "unknown")
            for s in src.split(" + "):
                s = s.strip()
                source_counts[s] = source_counts.get(s, 0) + 1

        # Count by language
        lang_counts = {}
        for j in jobs:
            lang = j.get("language", "unknown")
            lang_counts[lang] = lang_counts.get(lang, 0) + 1

        with col1:
            st.metric("Total Jobs", len(jobs))
        with col2:
            st.metric("Sources Used", len(source_counts))
        with col3:
            eng_count = lang_counts.get("English", 0) + lang_counts.get("English (German plus)", 0)
            st.metric("English-OK Jobs", eng_count)
        with col4:
            st.metric("German Jobs", lang_counts.get("German", 0))

        # --- Charts Row ---
        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.markdown("#### Jobs by Source")
            if source_counts:
                src_df = pd.DataFrame(
                    list(source_counts.items()),
                    columns=["Source", "Count"],
                ).sort_values("Count", ascending=True)
                st.bar_chart(src_df.set_index("Source"))

        with chart_col2:
            st.markdown("#### Jobs by Language")
            if lang_counts:
                lang_df = pd.DataFrame(
                    list(lang_counts.items()),
                    columns=["Language", "Count"],
                ).sort_values("Count", ascending=True)
                st.bar_chart(lang_df.set_index("Language"))

        st.divider()

        # --- Interactive Data Table ---
        st.markdown("### 📋 Job Results")

        # Prepare DataFrame for display
        display_cols = [
            "title", "company", "location", "source", "date_posted",
            "job_type", "experience_level", "is_remote", "language",
            "salary_min", "salary_max", "salary_currency", "job_url",
        ]
        if st.session_state.ai_scores_done:
            display_cols.insert(0, "ai_score")
        df = pd.DataFrame(jobs)
        available_cols = [c for c in display_cols if c in df.columns]
        display_df = df[available_cols].copy()

        # Configure column display
        column_config = {
            "ai_score": st.column_config.ProgressColumn(
                "AI Score",
                min_value=0,
                max_value=100,
                format="%d",
                width="small",
            ),
            "job_url": st.column_config.LinkColumn(
                "Job URL",
                display_text="Open →",
                width="medium",
            ),
            "title": st.column_config.TextColumn("Title", width="large"),
            "company": st.column_config.TextColumn("Company", width="medium"),
            "location": st.column_config.TextColumn("Location", width="medium"),
            "source": st.column_config.TextColumn("Source", width="small"),
            "date_posted": st.column_config.TextColumn("Posted", width="small"),
            "language": st.column_config.TextColumn("Language", width="small"),
            "is_remote": st.column_config.CheckboxColumn("Remote", width="small"),
            "salary_min": st.column_config.NumberColumn("Min Salary", format="%.0f"),
            "salary_max": st.column_config.NumberColumn("Max Salary", format="%.0f"),
        }

        st.dataframe(
            display_df,
            column_config=column_config,
            use_container_width=True,
            height=500,
            hide_index=True,
        )

        # --- Bookmarked Jobs ---
        bookmarked_count = len(st.session_state.bookmarked_jobs)
        if bookmarked_count > 0:
            with st.expander(f"⭐ Bookmarked Jobs ({bookmarked_count})", expanded=False):
                for j in jobs:
                    jk = j.get("job_url", "")
                    if jk in st.session_state.bookmarked_jobs:
                        bm_col1, bm_col2 = st.columns([5, 1])
                        with bm_col1:
                            st.write(f"**{j.get('title', 'Untitled')}** at {j.get('company', '?')} — {j.get('location', '')}")
                        with bm_col2:
                            if st.button("Remove", key=f"unbm_{jk[:40]}"):
                                st.session_state.bookmarked_jobs.discard(jk)
                                st.rerun()

        # --- Unified Job Detail Expanders with Pagination ---
        st.markdown("### 📄 Job Details")

        total_jobs = len(jobs)
        total_pages = max(1, (total_jobs + JOBS_PER_PAGE - 1) // JOBS_PER_PAGE)
        current_page = min(st.session_state.job_page, total_pages - 1)

        page_start = current_page * JOBS_PER_PAGE
        page_end = min(page_start + JOBS_PER_PAGE, total_jobs)

        st.caption(f"Showing jobs {page_start + 1}-{page_end} of {total_jobs}")

        scored = st.session_state.ai_scores_done

        for i in range(page_start, page_end):
            job = jobs[i]
            title = job.get("title", "Untitled")
            company = job.get("company", "Unknown")
            location_str = job.get("location", "")
            score = job.get("ai_score", 0)
            job_key = job.get("job_url", f"job_{i}")
            is_bookmarked = job_key in st.session_state.bookmarked_jobs

            if scored:
                if score >= 70:
                    badge = f"🟢 {score} High Match"
                elif score >= 40:
                    badge = f"🟡 {score} Medium Match"
                else:
                    badge = f"🔴 {score} Low Match"
                bm_icon = "⭐ " if is_bookmarked else ""
                label = f"{bm_icon}{badge} — **{title}** at {company} — {location_str}"
            else:
                bm_icon = "⭐ " if is_bookmarked else ""
                label = f"{bm_icon}**{title}** at {company} — {location_str}"

            with st.expander(label):
                # Bookmark + Track buttons
                bm_col, track_col = st.columns([1, 1])
                with bm_col:
                    bm_label = "Remove Bookmark" if is_bookmarked else "⭐ Bookmark"
                    if st.button(bm_label, key=f"bm_{i}"):
                        if is_bookmarked:
                            st.session_state.bookmarked_jobs.discard(job_key)
                        else:
                            st.session_state.bookmarked_jobs.add(job_key)
                        st.rerun()
                with track_col:
                    try:
                        from tracking.tracker import save_job as _save_tracked, get_job as _get_tracked, update_status as _update_tracked, VALID_STATUSES
                        tracked = _get_tracked(job_key)
                        if tracked:
                            current_status = tracked["status"]
                            new_status = st.selectbox(
                                "Status",
                                options=sorted(VALID_STATUSES),
                                index=sorted(VALID_STATUSES).index(current_status),
                                key=f"track_sel_{i}",
                                label_visibility="collapsed",
                            )
                            if new_status != current_status:
                                _update_tracked(job_key, new_status)
                                st.rerun()
                        else:
                            if st.button("💾 Save to Tracker", key=f"track_{i}"):
                                _save_tracked(
                                    job_url=job_key,
                                    title=title,
                                    company=company,
                                    location=location_str,
                                )
                                st.rerun()
                    except Exception:
                        pass

                if scored:
                    if score >= 70:
                        score_label = "High Match"
                    elif score >= 40:
                        score_label = "Medium Match"
                    else:
                        score_label = "Low Match"
                    st.markdown(f"**AI Score:** {score}/100 ({score_label})")
                    st.markdown(f"**Reasoning:** {job.get('ai_reasoning', 'N/A')}")

                    pros = job.get("ai_pros", [])
                    cons = job.get("ai_cons", [])
                    if pros or cons:
                        pro_col, con_col = st.columns(2)
                        with pro_col:
                            st.markdown("**Pros:**")
                            for p in pros:
                                st.markdown(f"- {p}")
                        with con_col:
                            st.markdown("**Cons:**")
                            for c in cons:
                                st.markdown(f"- {c}")

                    st.markdown("---")

                meta_col1, meta_col2, meta_col3 = st.columns(3)
                with meta_col1:
                    st.write(f"**Source:** {job.get('source', 'N/A')}")
                    st.write(f"**Posted:** {job.get('date_posted', 'N/A')}")
                with meta_col2:
                    st.write(f"**Type:** {job.get('job_type', 'N/A')}")
                    st.write(f"**Remote:** {'Yes' if job.get('is_remote') else 'No'}")
                with meta_col3:
                    st.write(f"**Language:** {job.get('language', 'N/A')}")
                    if job.get("salary_min"):
                        sal = f"{job['salary_currency'] or ''} {job['salary_min']:,.0f}"
                        if job.get("salary_max"):
                            sal += f" - {job['salary_max']:,.0f}"
                        st.write(f"**Salary:** {sal}")

                url = job.get("job_url")
                if url:
                    st.markdown(f"🔗 [Open Job Posting]({url})")

                desc = job.get("description", "")
                if desc:
                    st.markdown("---")
                    if "<" in desc and ">" in desc:
                        sanitized = bleach.clean(desc, tags=_SAFE_HTML_TAGS, attributes=_SAFE_HTML_ATTRS, strip=True)
                        st.html(f'<div style="max-height:400px;overflow-y:auto;font-size:0.9rem;">{sanitized}</div>')
                    else:
                        st.text(desc[:5000])
                else:
                    st.info("No description available.")

                # Cover letter (only when AI is configured and scoring is done)
                if scored and gemini_model and profile_text:
                    st.markdown("---")
                    job_lang = job.get("language", "English")
                    cover_lang = "German" if "German" in (job_lang or "") else "English"

                    if job_key in st.session_state.cover_letters:
                        st.markdown("**Generated Cover Letter:**")
                        letter = st.session_state.cover_letters[job_key]
                        st.text_area(
                            "Cover Letter",
                            value=letter,
                            height=300,
                            key=f"cl_display_{i}",
                            label_visibility="collapsed",
                        )
                        st.download_button(
                            "📥 Download Cover Letter",
                            data=letter,
                            file_name=f"cover_letter_{company.replace(' ', '_')}_{title.replace(' ', '_')[:30]}.txt",
                            mime="text/plain",
                            key=f"cl_download_{i}",
                        )
                    else:
                        if st.button(f"📝 Generate Cover Letter ({cover_lang})", key=f"cl_btn_{i}"):
                            from ai.cover_letter import generate_cover_letter
                            with st.spinner("Generating cover letter..."):
                                letter = generate_cover_letter(
                                    job, profile_text, gemini_model, language=cover_lang,
                                )
                            st.session_state.cover_letters[job_key] = letter
                            job["ai_cover_letter"] = letter
                            st.session_state.search_results = jobs
                            st.rerun()

                    # Resume tailoring
                    if job_key in st.session_state.resume_bullets:
                        st.markdown("**Tailored Resume Bullets:**")
                        bullets = st.session_state.resume_bullets[job_key]
                        st.text_area(
                            "Resume Bullets",
                            value=bullets,
                            height=300,
                            key=f"rb_display_{i}",
                            label_visibility="collapsed",
                        )
                        st.download_button(
                            "📥 Download Resume Bullets",
                            data=bullets,
                            file_name=f"resume_{company.replace(' ', '_')}_{title.replace(' ', '_')[:30]}.txt",
                            mime="text/plain",
                            key=f"rb_download_{i}",
                        )
                    else:
                        if st.button(f"📄 Tailor Resume ({cover_lang})", key=f"rb_btn_{i}"):
                            from ai.resume_tailor import generate_tailored_bullets
                            with st.spinner("Tailoring resume bullets..."):
                                bullets = generate_tailored_bullets(
                                    job, profile_text, gemini_model, language=cover_lang,
                                )
                            st.session_state.resume_bullets[job_key] = bullets
                            job["ai_resume_bullets"] = bullets
                            st.session_state.search_results = jobs
                            st.rerun()

        # Pagination controls
        if total_pages > 1:
            pg_col1, pg_col2, pg_col3 = st.columns([1, 3, 1])
            with pg_col1:
                if st.button("← Previous", disabled=(current_page == 0), key="pg_prev"):
                    st.session_state.job_page = max(0, current_page - 1)
                    st.rerun()
            with pg_col2:
                st.markdown(f"<div style='text-align:center'>Page {current_page + 1} of {total_pages}</div>", unsafe_allow_html=True)
            with pg_col3:
                if st.button("Next →", disabled=(current_page >= total_pages - 1), key="pg_next"):
                    st.session_state.job_page = min(total_pages - 1, current_page + 1)
                    st.rerun()

        # --- Download Buttons ---
        st.divider()
        st.markdown("### 📥 Download Results")
        dl_col1, dl_col2, dl_col3, dl_col4 = st.columns(4)

        with dl_col1:
            if filepath and os.path.exists(filepath):
                with open(filepath, "rb") as f:
                    st.download_button(
                        label="📊 Download Excel",
                        data=f,
                        file_name=os.path.basename(filepath),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )

        with dl_col2:
            csv_df = pd.DataFrame(jobs)
            csv_data = csv_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="📄 Download CSV",
                data=csv_data,
                file_name=f"jobs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True,
            )

        with dl_col3:
            import json as _json
            json_data = _json.dumps(jobs, ensure_ascii=False, indent=2, default=str).encode("utf-8")
            st.download_button(
                label="📋 Download JSON",
                data=json_data,
                file_name=f"jobs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True,
            )

        with dl_col4:
            if st.session_state.cover_letters:
                import io
                import zipfile
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                    for cl_key, cl_text in st.session_state.cover_letters.items():
                        safe_name = cl_key.split("/")[-1][:40].replace(" ", "_") if "/" in cl_key else cl_key[:40].replace(" ", "_")
                        zf.writestr(f"cover_letter_{safe_name}.txt", cl_text)
                st.download_button(
                    label=f"📦 All Cover Letters ({len(st.session_state.cover_letters)})",
                    data=zip_buffer.getvalue(),
                    file_name=f"cover_letters_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                    mime="application/zip",
                    use_container_width=True,
                )

    # =========================================================================
    # Company Registry Stats
    # =========================================================================
    try:
        from scrapers.company_registry import load_registry as _load_reg
        registry = _load_reg()
        total = len(registry.get("companies", {}))
        if total > 0:
            st.divider()
            st.markdown("### 📦 Company Registry")
            st.caption(f"Total companies tracked: {total}")

            ats_counts = {}
            for v in registry["companies"].values():
                ats = v.get("ats", "unknown")
                ats_counts[ats] = ats_counts.get(ats, 0) + 1

            cols = st.columns(len(ats_counts))
            for i, (ats, count) in enumerate(sorted(ats_counts.items(), key=lambda x: -x[1])):
                with cols[i % len(cols)]:
                    st.metric(ats.title(), count)

            recent = sorted(
                registry["companies"].values(),
                key=lambda x: x.get("discovered_date", ""),
                reverse=True,
            )[:10]

            if recent:
                with st.expander("🆕 Recently Discovered Companies"):
                    for company in recent:
                        st.text(f"{company.get('company_name', 'Unknown')} ({company['ats']}) "
                               f"— from {company.get('discovered_from', '?')}")
    except Exception as e:
        logger.debug("Company registry display failed: %s", e)

    # =========================================================================
    # AI Features — Scoring & Cover Letters
    # =========================================================================
    st.divider()
    st.markdown("### 🤖 AI Job Scoring & Cover Letters")

    if not gemini_api_key:
        st.warning("Enter your Gemini API key in the sidebar to enable AI features.")
    elif not profile_text:
        st.warning(
            "Paste your CV text in the sidebar, or create a `my_profile.txt` file "
            "in the project root, to enable AI scoring."
        )
    elif not gemini_model:
        st.error("Failed to initialize Gemini AI. Check your API key.")
    else:
        st.caption(f"Profile loaded ({len(profile_text)} characters)")

        # --- Score All Jobs ---
        score_col1, score_col2 = st.columns([2, 3])
        with score_col1:
            score_clicked = st.button(
                "🎯 Score All Jobs",
                type="primary",
                use_container_width=True,
                disabled=st.session_state.ai_scores_done,
            )
        with score_col2:
            if st.session_state.ai_scores_done:
                st.success("Scoring complete! Jobs are sorted by AI score.")
            else:
                st.caption(
                    f"Scores each job 1-100 against your profile using {active_model_name}. "
                    f"This takes ~{len(jobs) * 4 // 60 + 1} min for {len(jobs)} jobs."
                )

        if score_clicked and not st.session_state.ai_scores_done:
            from ai.scorer import score_jobs_batch

            progress_bar = st.progress(0, text="Starting AI scoring...")
            status_text = st.empty()

            def scoring_progress(msg: str) -> None:
                try:
                    import re as _re
                    m = _re.search(r"(\d+)-\d+ of (\d+)", msg)
                    if m:
                        current = int(m.group(1))
                        total_jobs = int(m.group(2))
                        pct = min(current / total_jobs, 0.99)
                        progress_bar.progress(pct, text=msg)
                    else:
                        status_text.caption(msg)
                except Exception as e:
                    logger.debug("Scoring progress update failed: %s", e)

            try:
                scored_jobs = score_jobs_batch(
                    jobs, profile_text, gemini_model, progress_callback=scoring_progress,
                )
                st.session_state.search_results = scored_jobs
                st.session_state.ai_scores_done = True
                progress_bar.progress(1.0, text="Scoring complete! Re-exporting Excel...")

                from output.excel_writer import write_excel
                new_filepath = write_excel(scored_jobs)
                st.session_state.output_filepath = new_filepath
                logger.info("Re-exported Excel with AI scores: %s", new_filepath)

                status_text.empty()
                st.rerun()
            except Exception as e:
                st.error(f"Scoring failed: {e}")
                logger.error("AI scoring failed: %s", e, exc_info=True)

        # --- Skills Extraction & Salary Estimation ---
        if st.session_state.ai_scores_done:
            st.divider()
            ai_extra_col1, ai_extra_col2 = st.columns(2)
            with ai_extra_col1:
                if st.button("🧠 Extract Skills", use_container_width=True, key="skills_btn"):
                    from processing.skills_extractor import extract_skills_batch
                    with st.spinner("Extracting skills from job descriptions..."):
                        extract_skills_batch(jobs, gemini_model)
                    st.session_state.search_results = jobs
                    st.success("Skills extracted!")
                    st.rerun()
            with ai_extra_col2:
                if st.button("💰 Estimate Salaries", use_container_width=True, key="salary_btn"):
                    from processing.salary_estimator import estimate_salaries
                    with st.spinner("Estimating salaries for jobs without salary data..."):
                        estimate_salaries(jobs, gemini_model)
                    st.session_state.search_results = jobs
                    st.success("Salary estimates added!")
                    st.rerun()

        # --- Scored Results Table ---
        if st.session_state.ai_scores_done:
            st.markdown("#### 🏆 Top Matches")

            scored_df_data = []
            for j in jobs:
                scored_df_data.append({
                    "Score": j.get("ai_score", 0),
                    "Title": j.get("title", ""),
                    "Company": j.get("company", ""),
                    "Location": j.get("location", ""),
                    "Language": j.get("language", ""),
                    "Reasoning": j.get("ai_reasoning", ""),
                })

            scored_df = pd.DataFrame(scored_df_data)

            def color_score(val):
                if isinstance(val, (int, float)):
                    if val >= 70:
                        return "background-color: #c6efce; color: #006100"
                    elif val >= 40:
                        return "background-color: #ffeb9c; color: #9c5700"
                    else:
                        return "background-color: #ffc7ce; color: #9c0006"
                return ""

            styled_df = scored_df.style.applymap(color_score, subset=["Score"])
            st.dataframe(
                styled_df,
                use_container_width=True,
                height=400,
                hide_index=True,
            )

# =============================================================================
# Application Tracker
# =============================================================================
try:
    from tracking.tracker import get_stats, get_all as get_all_tracked, VALID_STATUSES
    stats = get_stats()
    if stats.get("total", 0) > 0:
        st.divider()
        st.markdown("### 📊 Application Tracker")
        stat_cols = st.columns(len(stats))
        for i, (status, count) in enumerate(sorted(stats.items())):
            with stat_cols[i % len(stat_cols)]:
                st.metric(status.title(), count)

        tracker_filter = st.selectbox(
            "Filter by status",
            options=["All"] + sorted(VALID_STATUSES),
            key="tracker_filter",
        )
        tracked_jobs = get_all_tracked(tracker_filter if tracker_filter != "All" else None)
        if tracked_jobs:
            for tj in tracked_jobs[:20]:
                st.text(
                    f"[{tj['status'].upper()}] {tj['title']} at {tj['company']} "
                    f"— saved {tj['date_saved'][:10]}"
                )
except Exception as e:
    logger.debug("Application tracker display failed: %s", e)

# =============================================================================
# Footer
# =============================================================================
st.markdown("---")
st.caption("Job Finder v2.1 — India + Global support. Respect rate limits and terms of service.")
