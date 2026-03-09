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
    DEFAULT_SEARCH_TERM,
    DEFAULT_LOCATION,
    COUNTRIES,
    TIME_FILTER_OPTIONS,
    JOB_TYPE_OPTIONS,
    LANGUAGE_FILTER_OPTIONS,
    JOBSPY_SITES,
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


# =============================================================================
# Sidebar — Search Settings
# =============================================================================
with st.sidebar:
    st.markdown("## ⚙️ Search Settings")

    # Keywords & Location
    search_term = st.text_input("🔑 Job Title / Keywords", value=DEFAULT_SEARCH_TERM)
    location = st.text_input("📍 Location", value=DEFAULT_LOCATION)
    country = st.selectbox("🌍 Country", options=COUNTRIES, index=0)

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

    st.markdown("**Google Dorking (Company Career Pages)**")
    enable_dorking = st.checkbox(
        "Enable Google Dorking",
        value=True,
        help="Searches Google for job postings directly on company career pages and ATS platforms "
             "(Greenhouse, Lever, Workday, etc.). Discovers hidden jobs not listed on job boards.",
    )

    st.markdown("**Direct APIs**")
    col1, col2 = st.columns(2)
    with col1:
        use_arbeitnow = st.checkbox("Arbeitnow", value=True)
    with col2:
        use_remotive = st.checkbox("Remotive", value=False)

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

    # Advanced Dorking
    with st.expander("🔬 Advanced Dorking"):
        st.markdown("Add custom Google dork queries (one per line):")
        custom_dorks_text = st.text_area(
            "Custom Dork Queries",
            placeholder='site:example.com "software engineer" "Berlin"\ninurl:careers "python developer"',
            height=120,
            label_visibility="collapsed",
        )
        custom_dorks = [
            line.strip() for line in custom_dorks_text.strip().split("\n") if line.strip()
        ] if custom_dorks_text.strip() else None


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
    if enable_dorking:
        active_sources.append("Google Dorking")
    if use_arbeitnow:
        active_sources.append("Arbeitnow")
    if use_remotive:
        active_sources.append("Remotive")
    st.caption(f"Active sources: {' | '.join(active_sources)}")


# =============================================================================
# Run Search
# =============================================================================
if search_clicked:
    st.session_state.search_results = None
    st.session_state.output_filepath = None
    st.session_state.progress_messages = []

    # Set up logging for Streamlit
    from main import setup_logging, run_search
    setup_logging()

    progress_container = st.container()
    progress_bar = st.progress(0, text="Initializing search...")
    status_area = st.empty()

    step_count = [0]
    total_steps = sum([enable_jobspy, enable_dorking, use_arbeitnow, use_remotive]) + 4  # +4 for post-processing

    def streamlit_progress(msg: str) -> None:
        """Update progress in the Streamlit UI."""
        st.session_state.progress_messages.append(msg)
        step_count[0] += 0.5
        progress_pct = min(step_count[0] / (total_steps * 3), 0.98)
        progress_bar.progress(progress_pct, text=msg[:100])

    try:
        with st.spinner("Searching for jobs..."):
            jobs, filepath = run_search(
                search_term=search_term,
                location=location,
                country=country,
                hours_old=hours_old,
                results_per_site=results_per_site,
                job_type=job_type,
                is_remote=is_remote,
                language_filter=language_filter,
                enable_jobspy=enable_jobspy,
                jobspy_sites=jobspy_sites if enable_jobspy else None,
                enable_google_dorking=enable_dorking,
                enable_arbeitnow=use_arbeitnow,
                enable_remotive=use_remotive,
                output_format="excel",
                custom_dorks=custom_dorks,
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
        for msg in st.session_state.progress_messages:
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
            st.metric("English Jobs", lang_counts.get("English", 0))
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
            "job_type", "is_remote", "language", "salary_min", "salary_max",
            "salary_currency", "job_url",
        ]
        df = pd.DataFrame(jobs)
        available_cols = [c for c in display_cols if c in df.columns]
        display_df = df[available_cols].copy()

        # Configure column display
        column_config = {
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

        # --- Job Detail Expanders ---
        st.markdown("### 📄 Job Descriptions")
        st.caption("Click on a job to expand and view its full description.")

        for i, job in enumerate(jobs[:50]):  # Limit to first 50 for performance
            title = job.get("title", "Untitled")
            company = job.get("company", "Unknown")
            location = job.get("location", "")
            with st.expander(f"**{title}** at {company} — {location}"):
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
                    # Render as HTML if it contains HTML tags, otherwise as text
                    if "<" in desc and ">" in desc:
                        st.html(f'<div style="max-height:400px;overflow-y:auto;font-size:0.9rem;">{desc}</div>')
                    else:
                        st.text(desc[:5000])
                else:
                    st.info("No description available.")

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
    # Phase 2 Placeholder
    # =========================================================================
    st.divider()
    st.markdown("### 🤖 AI Features — Coming in Phase 2")
    st.markdown(
        """
        <div style="background-color: #f0f0f0; border-radius: 10px; padding: 20px;
                    border: 2px dashed #ccc; color: #999; text-align: center;">
            <h4 style="color: #999;">Powered by Google Gemini AI</h4>
            <p>🎯 <b>Job Scoring</b> — Rate each job against your profile (1-100)</p>
            <p>📝 <b>Cover Letter Generation</b> — AI-written tailored cover letters</p>
            <p>📄 <b>Resume Tailoring</b> — Custom bullet points for each job</p>
            <p style="margin-top: 15px; font-size: 0.9rem;">
                Fill in <code>my_profile.json</code> with your resume data to prepare for Phase 2.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

# =============================================================================
# Footer
# =============================================================================
st.markdown("---")
st.caption("Job Finder v1.0 — Built for personal use. Respect rate limits and terms of service.")
