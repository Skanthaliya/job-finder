"""Tests for processing/language_detector.py — regex pattern matching for language detection."""

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from processing.language_detector import (
    detect_language,
    _detect_from_title,
    detect_languages_batch,
)


class TestDetectFromTitle:
    def test_german_gender_marker(self):
        assert _detect_from_title("Product Owner (m/w/d)") == "German"

    def test_german_werkstudent(self):
        assert _detect_from_title("Werkstudent IT") == "German"

    def test_english_title(self):
        assert _detect_from_title("Product Manager") == "unknown"

    def test_empty(self):
        assert _detect_from_title("") == "unknown"


class TestDetectLanguage:
    def test_none_text(self):
        result = detect_language(None, "Product Owner (m/w/d)")
        assert result == "German"

    def test_empty_text_with_title(self):
        result = detect_language("", "Product Owner (m/w/d)")
        assert result == "German"

    def test_english_explicit_no_german(self):
        text = "We are looking for a Product Owner. No German required. Working language is English."
        result = detect_language(text)
        assert result == "English"

    def test_german_required(self):
        text = "We need a Product Owner. Fluent German is required for this position."
        result = detect_language(text)
        assert result == "German"

    def test_german_optional(self):
        text = "We are looking for a Product Owner. English is the working language. German is a plus."
        result = detect_language(text)
        assert result == "English (German plus)"

    def test_german_text(self):
        text = (
            "Wir suchen einen erfahrenen Product Owner für unser Team in Berlin. "
            "Sie werden verantwortlich sein für die Produktentwicklung und das Backlog-Management. "
            "Fließende Deutschkenntnisse sind erforderlich."
        )
        result = detect_language(text)
        assert result == "German"

    def test_english_working_language(self):
        text = (
            "Join our international team. The working language is English. "
            "We build great products in an English-speaking environment."
        )
        result = detect_language(text)
        assert result == "English"

    def test_french_required(self):
        text = "We need someone with fluent French for our Paris office. French is required."
        result = detect_language(text)
        assert result == "French"

    def test_german_nice_to_have_patterns(self):
        text = "English is our working language. German is beneficial but not required."
        result = detect_language(text)
        assert "English" in result

    def test_german_b2_required(self):
        text = "Requirements: German C1 level, experience in agile methodologies."
        result = detect_language(text)
        assert result == "German"

    def test_deutschkenntnisse_von_vorteil(self):
        text = "We are hiring a developer. English required. Deutschkenntnisse von Vorteil."
        result = detect_language(text)
        assert result == "English (German plus)"


class TestDetectLanguagesBatch:
    def test_batch(self):
        jobs = [
            {"title": "Product Owner", "description": "English working language. No German required."},
            {"title": "Projektleiter (m/w/d)", "description": "Fließende Deutschkenntnisse erforderlich."},
        ]
        result = detect_languages_batch(jobs)
        assert result[0]["language"] == "English"
        assert result[1]["language"] == "German"

    def test_empty_batch(self):
        assert detect_languages_batch([]) == []

    def test_missing_description(self):
        jobs = [{"title": "Product Owner (m/w/d)"}]
        result = detect_languages_batch(jobs)
        assert result[0]["language"] == "German"
