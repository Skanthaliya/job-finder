"""
output/excel_writer.py — Write job results to formatted .xlsx files.

Creates a multi-sheet Excel workbook with:
- Sheet 1: Jobs Summary (all fields except long text fields)
- Sheet 2: Full Details (all fields including description)
- Sheet 3: AI Results (placeholder for Phase 2)
"""

import logging
import os
from datetime import datetime

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

from config import OUTPUT_DIR

logger = logging.getLogger(__name__)

# Color scheme for different sources
SOURCE_COLORS = {
    "indeed": "E8F5E9",       # Light green
    "linkedin": "E3F2FD",     # Light blue
    "google": "FFF3E0",       # Light orange
    "glassdoor": "F3E5F5",    # Light purple
    "zip_recruiter": "E0F7FA", # Light cyan
    "google_dork": "FFF9C4",  # Light yellow
    "arbeitnow": "FCE4EC",    # Light pink
    "remotive": "E8EAF6",     # Light indigo
}

# Summary columns (exclude long text fields)
SUMMARY_COLUMNS = [
    "source", "ats_platform", "title", "company", "location", "country",
    "date_posted", "job_type", "is_remote", "salary_min", "salary_max",
    "salary_currency", "salary_interval", "job_url", "company_url", "language",
]

# AI columns for Sheet 3
AI_COLUMNS = [
    "title", "company", "job_url", "ai_score", "ai_reasoning",
    "ai_cover_letter", "ai_resume_bullets",
]


def write_excel(jobs: list[dict], filename: str | None = None) -> str:
    """
    Write job results to a formatted Excel file.

    Args:
        jobs: List of job dicts (unified schema).
        filename: Optional filename. Defaults to jobs_YYYYMMDD_HHMMSS.xlsx.

    Returns:
        The filepath of the created Excel file.
    """
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"jobs_{timestamp}.xlsx"

    filepath = os.path.join(OUTPUT_DIR, filename)

    if not jobs:
        logger.warning("No jobs to write to Excel.")
        # Create an empty file with headers
        df = pd.DataFrame(columns=SUMMARY_COLUMNS)
        df.to_excel(filepath, index=False, sheet_name="Jobs Summary")
        logger.info("Created empty Excel file: %s", filepath)
        return filepath

    logger.info("Writing %d jobs to Excel: %s", len(jobs), filepath)

    # Sort by date_posted descending (newest first)
    sorted_jobs = sorted(
        jobs,
        key=lambda j: j.get("date_posted") or "0000-00-00",
        reverse=True,
    )

    # Create DataFrames
    df_full = pd.DataFrame(sorted_jobs)
    df_summary = df_full[[c for c in SUMMARY_COLUMNS if c in df_full.columns]].copy()
    df_ai = df_full[[c for c in AI_COLUMNS if c in df_full.columns]].copy()

    # Write to Excel with multiple sheets
    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        df_summary.to_excel(writer, sheet_name="Jobs Summary", index=False)
        df_full.to_excel(writer, sheet_name="Full Details", index=False)
        df_ai.to_excel(writer, sheet_name="AI Results", index=False)

    # Now apply formatting with openpyxl
    wb = load_workbook(filepath)
    _format_summary_sheet(wb["Jobs Summary"], sorted_jobs)
    _format_full_details_sheet(wb["Full Details"])
    _format_ai_sheet(wb["AI Results"])

    wb.save(filepath)
    logger.info("Excel file saved: %s", filepath)
    return filepath


def _format_summary_sheet(ws, jobs: list[dict]) -> None:
    """Apply formatting to the Jobs Summary sheet."""
    if ws.max_row <= 1:
        return

    # Header styling
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    for col_idx in range(1, ws.max_column + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border

    # Freeze top row
    ws.freeze_panes = "A2"

    # Find the job_url column and source column indices
    header_values = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]
    url_col_idx = None
    source_col_idx = None

    for idx, val in enumerate(header_values):
        if val == "job_url":
            url_col_idx = idx + 1
        if val == "source":
            source_col_idx = idx + 1

    # Apply row formatting
    for row_idx in range(2, ws.max_row + 1):
        # Color-code by source
        if source_col_idx:
            source_val = ws.cell(row=row_idx, column=source_col_idx).value or ""
            # Check the first source (in case of combined sources)
            primary_source = source_val.split(" + ")[0].strip().lower() if source_val else ""
            color = SOURCE_COLORS.get(primary_source, "FFFFFF")
            row_fill = PatternFill(start_color=color, end_color=color, fill_type="solid")
            for col_idx in range(1, ws.max_column + 1):
                ws.cell(row=row_idx, column=col_idx).fill = row_fill
                ws.cell(row=row_idx, column=col_idx).border = thin_border

        # Make job_url a hyperlink
        if url_col_idx:
            url_cell = ws.cell(row=row_idx, column=url_col_idx)
            url_val = url_cell.value
            if url_val and isinstance(url_val, str) and url_val.startswith("http"):
                url_cell.hyperlink = url_val
                url_cell.font = Font(color="0563C1", underline="single")
                # Truncate display text if too long
                if len(url_val) > 60:
                    url_cell.value = url_val[:57] + "..."

    # Auto-size columns
    for col_idx in range(1, ws.max_column + 1):
        max_width = 10
        for row_idx in range(1, min(ws.max_row + 1, 100)):  # Sample first 100 rows
            cell_value = ws.cell(row=row_idx, column=col_idx).value
            if cell_value:
                max_width = max(max_width, len(str(cell_value)))
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max_width + 2, 50)


def _format_full_details_sheet(ws) -> None:
    """Apply basic formatting to the Full Details sheet."""
    if ws.max_row <= 1:
        return

    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)

    for col_idx in range(1, ws.max_column + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    ws.freeze_panes = "A2"

    # Auto-size (with lower cap since description can be very long)
    for col_idx in range(1, ws.max_column + 1):
        header = ws.cell(row=1, column=col_idx).value or ""
        if header in ("description", "ai_cover_letter", "ai_resume_bullets"):
            ws.column_dimensions[get_column_letter(col_idx)].width = 50
        else:
            max_width = len(str(header)) + 2
            for row_idx in range(2, min(ws.max_row + 1, 50)):
                val = ws.cell(row=row_idx, column=col_idx).value
                if val:
                    max_width = max(max_width, len(str(val)))
            ws.column_dimensions[get_column_letter(col_idx)].width = min(max_width + 2, 40)

    # Wrap text in description column
    header_values = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]
    for idx, val in enumerate(header_values):
        if val in ("description", "ai_cover_letter", "ai_resume_bullets"):
            col_letter = get_column_letter(idx + 1)
            for row_idx in range(2, ws.max_row + 1):
                ws.cell(row=row_idx, column=idx + 1).alignment = Alignment(wrap_text=True, vertical="top")


def _format_ai_sheet(ws) -> None:
    """Apply formatting to the AI Results placeholder sheet."""
    header_fill = PatternFill(start_color="FF9800", end_color="FF9800", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)

    for col_idx in range(1, ws.max_column + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    ws.freeze_panes = "A2"

    # Add a note in cell A2 if the sheet only has headers
    if ws.max_row <= 1:
        ws.cell(row=2, column=1).value = "AI scoring and generation will be available in Phase 2"
        ws.cell(row=2, column=1).font = Font(italic=True, color="808080")

    # Auto-size
    for col_idx in range(1, ws.max_column + 1):
        header = ws.cell(row=1, column=col_idx).value or ""
        ws.column_dimensions[get_column_letter(col_idx)].width = max(len(str(header)) + 4, 15)
