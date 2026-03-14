"""
tracking/tracker.py — SQLite-based job application status tracking.

Stores application status, dates, notes, and cover letters for each job URL.
Turns the tool from "find jobs" into "find and track jobs."
"""

import logging
import os
import sqlite3
from datetime import datetime

from config import OUTPUT_DIR

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(OUTPUT_DIR, "job_tracker.db")

VALID_STATUSES = {"saved", "applied", "interviewing", "rejected", "offered", "accepted"}


def _get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            job_url       TEXT PRIMARY KEY,
            title         TEXT,
            company       TEXT,
            location      TEXT,
            status        TEXT NOT NULL DEFAULT 'saved',
            date_saved    TEXT NOT NULL,
            date_applied  TEXT,
            notes         TEXT DEFAULT '',
            cover_letter  TEXT DEFAULT '',
            updated_at    TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def save_job(
    job_url: str,
    title: str = "",
    company: str = "",
    location: str = "",
    status: str = "saved",
    notes: str = "",
    cover_letter: str = "",
) -> None:
    """Save or update a job in the tracker."""
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}. Must be one of {VALID_STATUSES}")

    now = datetime.now().isoformat()
    conn = _get_connection()
    try:
        existing = conn.execute(
            "SELECT * FROM applications WHERE job_url = ?", (job_url,)
        ).fetchone()

        if existing:
            date_applied = existing["date_applied"]
            if status == "applied" and not date_applied:
                date_applied = now

            conn.execute("""
                UPDATE applications
                SET status = ?, notes = ?, cover_letter = ?, date_applied = ?, updated_at = ?
                WHERE job_url = ?
            """, (status, notes or existing["notes"], cover_letter or existing["cover_letter"],
                  date_applied, now, job_url))
        else:
            date_applied = now if status == "applied" else None
            conn.execute("""
                INSERT INTO applications
                    (job_url, title, company, location, status, date_saved, date_applied, notes, cover_letter, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (job_url, title, company, location, status, now, date_applied, notes, cover_letter, now))

        conn.commit()
    finally:
        conn.close()


def update_status(job_url: str, status: str) -> bool:
    """Update the status of a tracked job. Returns True if the job existed."""
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}. Must be one of {VALID_STATUSES}")

    now = datetime.now().isoformat()
    conn = _get_connection()
    try:
        extra_set = ""
        if status == "applied":
            extra_set = ", date_applied = COALESCE(date_applied, ?)"

        if extra_set:
            cursor = conn.execute(
                f"UPDATE applications SET status = ?, updated_at = ?{extra_set} WHERE job_url = ?",
                (status, now, now, job_url),
            )
        else:
            cursor = conn.execute(
                "UPDATE applications SET status = ?, updated_at = ? WHERE job_url = ?",
                (status, now, job_url),
            )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def update_notes(job_url: str, notes: str) -> bool:
    """Update notes for a tracked job."""
    now = datetime.now().isoformat()
    conn = _get_connection()
    try:
        cursor = conn.execute(
            "UPDATE applications SET notes = ?, updated_at = ? WHERE job_url = ?",
            (notes, now, job_url),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_job(job_url: str) -> dict | None:
    """Get tracking info for a single job URL."""
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM applications WHERE job_url = ?", (job_url,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_all(status_filter: str | None = None) -> list[dict]:
    """Get all tracked jobs, optionally filtered by status."""
    conn = _get_connection()
    try:
        if status_filter and status_filter in VALID_STATUSES:
            rows = conn.execute(
                "SELECT * FROM applications WHERE status = ? ORDER BY updated_at DESC",
                (status_filter,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM applications ORDER BY updated_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_stats() -> dict:
    """Get summary statistics of tracked applications."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM applications GROUP BY status"
        ).fetchall()
        stats = {row["status"]: row["cnt"] for row in rows}
        stats["total"] = sum(stats.values())
        return stats
    finally:
        conn.close()


def delete_job(job_url: str) -> bool:
    """Remove a job from the tracker."""
    conn = _get_connection()
    try:
        cursor = conn.execute("DELETE FROM applications WHERE job_url = ?", (job_url,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()
