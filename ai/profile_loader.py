"""
ai/profile_loader.py — Load user profile text for AI features.

Priority (highest first):
  1. Text pasted directly in the Streamlit sidebar text box
  2. Fallback to my_profile.txt (plain text file with all CVs copy-pasted)
  3. Fallback to my_profile.json (structured JSON -> flattened to text)
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

PROFILE_TXT_PATH = "my_profile.txt"
PROFILE_JSON_PATH = "my_profile.json"


def load_profile(sidebar_text: str = "") -> str:
    """Return profile text from the best available source.

    Args:
        sidebar_text: Text pasted by the user in the Streamlit text box.

    Returns:
        Profile text string, or empty string if nothing is available.
    """
    text = sidebar_text.strip()
    if text:
        logger.info("Using profile text from sidebar (%d chars)", len(text))
        return text

    text = _load_from_txt()
    if text:
        logger.info("Using profile text from %s (%d chars)", PROFILE_TXT_PATH, len(text))
        return text

    text = _load_from_json()
    if text:
        logger.info("Using profile text from %s (%d chars)", PROFILE_JSON_PATH, len(text))
        return text

    logger.warning("No profile text found — paste your CV in the sidebar or create %s", PROFILE_TXT_PATH)
    return ""


def _load_from_txt() -> str:
    if not os.path.exists(PROFILE_TXT_PATH):
        return ""
    try:
        with open(PROFILE_TXT_PATH, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        logger.error("Failed to read %s: %s", PROFILE_TXT_PATH, e)
        return ""


def _load_from_json() -> str:
    if not os.path.exists(PROFILE_JSON_PATH):
        return ""
    try:
        with open(PROFILE_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return _json_profile_to_text(data)
    except Exception as e:
        logger.error("Failed to read %s: %s", PROFILE_JSON_PATH, e)
        return ""


def _json_profile_to_text(data: dict) -> str:
    """Flatten the structured my_profile.json into readable text for the LLM."""
    if data.get("name", "").startswith("Your "):
        return ""

    parts = []

    if data.get("name"):
        parts.append(f"Name: {data['name']}")
    if data.get("location"):
        parts.append(f"Location: {data['location']}")
    if data.get("summary"):
        parts.append(f"\nSummary:\n{data['summary']}")

    if data.get("skills"):
        parts.append(f"\nSkills: {', '.join(data['skills'])}")

    if data.get("experience"):
        parts.append("\nExperience:")
        for exp in data["experience"]:
            parts.append(f"  {exp.get('title', '')} at {exp.get('company', '')} ({exp.get('dates', '')})")
            for bullet in exp.get("bullets", []):
                parts.append(f"    - {bullet}")

    if data.get("education"):
        parts.append("\nEducation:")
        for edu in data["education"]:
            parts.append(f"  {edu.get('degree', '')} — {edu.get('school', '')} ({edu.get('year', '')})")

    if data.get("certifications"):
        parts.append(f"\nCertifications: {', '.join(data['certifications'])}")

    if data.get("languages_spoken"):
        parts.append(f"\nLanguages: {', '.join(data['languages_spoken'])}")

    if data.get("preferred_work_style"):
        parts.append(f"\nPreferred work style: {data['preferred_work_style']}")

    if data.get("visa_status"):
        parts.append(f"Visa status: {data['visa_status']}")

    return "\n".join(parts).strip()
