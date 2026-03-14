"""Tests for processing/deduplicator.py — URL normalization, title matching, merge logic."""

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from processing.deduplicator import (
    deduplicate,
    _normalize_url,
    _normalize_title,
    _normalize_company,
    _merge_jobs,
    _data_completeness_score,
)


class TestNormalizeUrl:
    def test_empty(self):
        assert _normalize_url("") == ""

    def test_strips_query_and_fragment(self):
        result = _normalize_url("https://example.com/job/123?ref=google#apply")
        assert "ref=google" not in result
        assert "#apply" not in result

    def test_strips_trailing_slash(self):
        result = _normalize_url("https://example.com/job/123/")
        assert result.endswith("123")

    def test_lowercases_host(self):
        result = _normalize_url("https://EXAMPLE.COM/Job/123")
        assert "example.com" in result

    def test_preserves_path_case(self):
        result = _normalize_url("https://example.com/Job/123")
        assert "/Job/123" in result

    def test_non_http(self):
        result = _normalize_url("ftp://example.com/file")
        assert result == "ftp://example.com/file"


class TestNormalizeTitle:
    def test_empty(self):
        assert _normalize_title("") == ""

    def test_expands_sr(self):
        assert "senior" in _normalize_title("Sr. Product Owner")

    def test_expands_jr(self):
        assert "junior" in _normalize_title("Jr Developer")

    def test_strips_gender_markers(self):
        result = _normalize_title("Product Owner (m/w/d)")
        assert "(m/w/d)" not in result
        assert "product owner" in result

    def test_strips_all_genders(self):
        result = _normalize_title("Scrum Master (all genders)")
        assert "(all genders)" not in result

    def test_normalizes_whitespace(self):
        result = _normalize_title("Product   Owner   (m/w/d)")
        assert "  " not in result

    def test_expands_pm(self):
        assert "product manager" in _normalize_title("PM")

    def test_expands_po(self):
        assert "product owner" in _normalize_title("PO")


class TestNormalizeCompany:
    def test_empty(self):
        assert _normalize_company("") == ""

    def test_strips_gmbh(self):
        result = _normalize_company("SAP GmbH")
        assert "gmbh" not in result.lower()
        assert "sap" in result

    def test_strips_inc(self):
        result = _normalize_company("Google Inc.")
        assert "inc" not in result.lower()

    def test_strips_ag(self):
        result = _normalize_company("Siemens AG")
        assert "ag" not in result.lower()

    def test_strips_ltd(self):
        result = _normalize_company("Acme Ltd")
        assert "ltd" not in result.lower()

    def test_preserves_core_name(self):
        result = _normalize_company("Deutsche Telekom AG")
        assert "deutsche telekom" in result


class TestMergeJobs:
    def test_keeps_longer_description(self):
        existing = {"title": "PO", "description": "Short"}
        new = {"title": "PO", "description": "A much longer and more detailed description of the role"}
        merged = _merge_jobs(existing, new)
        assert merged["description"] == new["description"]

    def test_combines_sources(self):
        existing = {"title": "PO", "source": "indeed"}
        new = {"title": "PO", "source": "greenhouse"}
        merged = _merge_jobs(existing, new)
        assert "indeed" in merged["source"]
        assert "greenhouse" in merged["source"]

    def test_fills_none_fields(self):
        existing = {"title": "PO", "salary_min": None, "source": "indeed"}
        new = {"title": "PO", "salary_min": 50000, "source": "greenhouse"}
        merged = _merge_jobs(existing, new)
        assert merged["salary_min"] == 50000

    def test_prefers_ats_source(self):
        existing = {"title": "PO", "source": "indeed", "description": "Short"}
        new = {"title": "PO", "source": "ats_discovery", "ats_platform": "greenhouse", "description": "Short"}
        merged = _merge_jobs(existing, new)
        assert "ats_discovery" in merged["source"]


class TestDataCompletenessScore:
    def test_empty_job(self):
        assert _data_completeness_score({}) == 0

    def test_full_job(self):
        job = {
            "title": "PO",
            "company": "SAP",
            "location": "Berlin",
            "description": "x" * 3000,
            "date_posted": "2024-01-01",
            "salary_min": 50000,
            "job_type": "fulltime",
            "is_remote": True,
            "country": "Germany",
            "company_url": "https://sap.com",
        }
        score = _data_completeness_score(job)
        assert score >= 15


class TestDeduplicate:
    def test_empty(self):
        assert deduplicate([]) == []

    def test_no_duplicates(self):
        jobs = [
            {"title": "PO", "company": "A", "job_url": "https://a.com/1"},
            {"title": "PM", "company": "B", "job_url": "https://b.com/2"},
        ]
        assert len(deduplicate(jobs)) == 2

    def test_url_dedup(self):
        jobs = [
            {"title": "PO", "company": "A", "job_url": "https://example.com/job/1"},
            {"title": "PO", "company": "A", "job_url": "https://example.com/job/1?ref=google"},
        ]
        assert len(deduplicate(jobs)) == 1

    def test_title_company_dedup(self):
        jobs = [
            {"title": "Product Owner", "company": "SAP GmbH", "job_url": "https://a.com/1"},
            {"title": "Product Owner", "company": "SAP", "job_url": "https://b.com/2"},
        ]
        assert len(deduplicate(jobs)) == 1

    def test_abbreviation_dedup(self):
        jobs = [
            {"title": "Sr. Product Owner (m/w/d)", "company": "SAP", "job_url": "https://a.com/1"},
            {"title": "Senior Product Owner", "company": "SAP GmbH", "job_url": "https://b.com/2"},
        ]
        assert len(deduplicate(jobs)) == 1
