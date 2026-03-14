"""
scrapers/ats/utils.py — Shared utilities for ATS scrapers.
"""

import re
from html import unescape


def strip_html(html_text: str) -> str:
    """Strip HTML tags from text, preserving basic structure."""
    text = re.sub(r"<br\s*/?>", "\n", html_text)
    text = re.sub(r"<p>", "\n", text)
    text = re.sub(r"</p>", "\n", text)
    text = re.sub(r"<li>", "\n• ", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
