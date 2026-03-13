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
    GEMINI_API_KEY,
    GEMINI_MODEL,
)

logger = logging.getLogger(__name__)

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
        color: #1a73e8;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        text-align: center;
        border: 1px solid #e0e0e0;
    }
    .stButton > button[kind="primary"] {
        width: 100%;
        font-size: 1.2rem;
        padding: 0.75rem;
    }
    div[data-testid="stExpander"] details summary p {
        font-size: 1rem;
    }
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
        use_google_jobs = st.checkbox("Google Jobs", value=True)
    with col2:
        use_glassdoor = st.checkbox("Glassdoor", value=False)
        use_ziprecruiter = st.checkbox("ZipRecruiter", value=False)

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
    with col2:
        use_remotive = st.checkbox("Remotive", value=False)

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
        except Exception:
            pass

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

    # Set up logging for Streamlit
    from main import setup_logging, run_search
    setup_logging()

    progress_container = st.container()
    progress_bar = st.progress(0, text="Initializing search...")
    status_area = st.empty()

    step_count = [0]
    total_steps = sum([enable_jobspy, enable_ats_discovery, use_arbeitnow, use_remotive, enable_serpapi]) + 4
    progress_log = []  # Thread-safe regular list instead of session_state

    def streamlit_progress(msg: str) -> None:
        """Update progress in the Streamlit UI (thread-safe)."""
        try:
            progress_log.append(msg)
            step_count[0] += 0.5
            progress_pct = min(step_count[0] / (total_steps * 3), 0.98)
            progress_bar.progress(progress_pct, text=msg[:100])
        except Exception:
            pass  # Silently ignore progress update failures from threads

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
        if gemini_api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=gemini_api_key)
                gemini_model = genai.GenerativeModel(GEMINI_MODEL)
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

        # --- Unified Job Detail Expanders ---
        st.markdown("### 📄 Job Details")
        st.caption("Click on a job to expand and view its full description.")

        scored = st.session_state.ai_scores_done

        for i, job in enumerate(jobs[:50]):
            title = job.get("title", "Untitled")
            company = job.get("company", "Unknown")
            location_str = job.get("location", "")
            score = job.get("ai_score", 0)

            if scored:
                if score >= 70:
                    badge = f"🟢 {score}"
                elif score >= 40:
                    badge = f"🟡 {score}"
                else:
                    badge = f"🔴 {score}"
                label = f"{badge} — **{title}** at {company} — {location_str}"
            else:
                label = f"**{title}** at {company} — {location_str}"

            with st.expander(label):
                if scored:
                    st.markdown(f"**AI Score:** {score}/100")
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
                        st.html(f'<div style="max-height:400px;overflow-y:auto;font-size:0.9rem;">{desc}</div>')
                    else:
                        st.text(desc[:5000])
                else:
                    st.info("No description available.")

                # Cover letter (only when AI is configured and scoring is done)
                if scored and gemini_model and profile_text:
                    st.markdown("---")
                    job_lang = job.get("language", "English")
                    cover_lang = "German" if "German" in (job_lang or "") else "English"
                    job_key = job.get("job_url", f"job_{i}")

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

        if len(jobs) > 50:
            st.info(f"Showing first 50 of {len(jobs)} jobs. Download the Excel file for all results.")

        # --- Download Buttons ---
        st.divider()
        st.markdown("### 📥 Download Results")
        dl_col1, dl_col2 = st.columns(2)

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
            # Generate CSV on-the-fly for download
            csv_df = pd.DataFrame(jobs)
            csv_data = csv_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="📄 Download CSV",
                data=csv_data,
                file_name=f"jobs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
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
    except Exception:
        pass

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
                    f"Scores each job 1-100 against your profile using {GEMINI_MODEL}. "
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
                except Exception:
                    pass

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
# Footer
# =============================================================================
st.markdown("---")
st.caption("Job Finder v1.0 — Built for personal use. Respect rate limits and terms of service.")
