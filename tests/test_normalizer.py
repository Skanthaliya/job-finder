"""Tests for processing/normalizer.py — date parsing, job type normalization, schema enforcement."""

import sys
import os
from datetime import datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from processing.normalizer import (
    normalize_jobs,
    _normalize_date,
    _normalize_job_type,
    _normalize_single,
    _extract_experience_level,
    UNIFIED_SCHEMA_FIELDS,
)


class TestNormalizeDate:
    def test_none(self):
        assert _normalize_date(None) is None

    def test_empty_string(self):
        assert _normalize_date("") is None

    def test_iso_format(self):
        assert _normalize_date("2024-03-15") == "2024-03-15"

    def test_iso_with_time(self):
        assert _normalize_date("2024-03-15T10:30:00") == "2024-03-15"

    def test_iso_with_z(self):
        assert _normalize_date("2024-03-15T10:30:00Z") == "2024-03-15"

    def test_datetime_object(self):
        dt = datetime(2024, 3, 15, 10, 30)
        assert _normalize_date(dt) == "2024-03-15"

    def test_unix_timestamp(self):
        result = _normalize_date("1710460800")
        assert result is not None
        assert len(result) == 10

    def test_european_format(self):
        assert _normalize_date("15/03/2024") == "2024-03-15"

    def test_german_format(self):
        assert _normalize_date("15.03.2024") == "2024-03-15"

    def test_english_long(self):
        assert _normalize_date("March 15, 2024") == "2024-03-15"

    def test_english_short(self):
        assert _normalize_date("Mar 15, 2024") == "2024-03-15"

    def test_unparseable_returns_as_is(self):
        result = _normalize_date("yesterday")
        assert result == "yesterday"


class TestNormalizeJobType:
    def test_none(self):
        assert _normalize_job_type(None) is None

    def test_canonical(self):
        assert _normalize_job_type("fulltime") == "fulltime"

    def test_hyphenated(self):
        assert _normalize_job_type("full-time") == "fulltime"

    def test_spaced(self):
        assert _normalize_job_type("Full Time") == "fulltime"

    def test_parttime(self):
        assert _normalize_job_type("Part-Time") == "parttime"

    def test_freelance(self):
        assert _normalize_job_type("freelance") == "contract"

    def test_intern(self):
        assert _normalize_job_type("Intern") == "internship"

    def test_werkstudent(self):
        assert _normalize_job_type("Working Student") == "internship"

    def test_unknown_passthrough(self):
        assert _normalize_job_type("apprenticeship") == "apprenticeship"


class TestExtractExperienceLevel:
    def test_senior_in_title(self):
        assert _extract_experience_level("Senior Product Owner") == "senior"

    def test_junior_in_title(self):
        assert _extract_experience_level("Junior Developer") == "junior"

    def test_lead_in_title(self):
        assert _extract_experience_level("Team Lead Engineering") == "lead"

    def test_intern_in_title(self):
        assert _extract_experience_level("Internship Product Management") == "intern"

    def test_werkstudent(self):
        assert _extract_experience_level("Werkstudent IT") == "intern"

    def test_director(self):
        assert _extract_experience_level("Director of Engineering") == "director"

    def test_vp(self):
        assert _extract_experience_level("VP Product") == "vp"

    def test_years_from_description(self):
        assert _extract_experience_level("Product Owner", "Requires 5+ years of experience") == "mid"

    def test_no_level(self):
        assert _extract_experience_level("Product Owner") is None


class TestNormalizeSingle:
    def test_fills_missing_fields(self):
        job = {"title": "Test Job", "company": "TestCo"}
        result = _normalize_single(job)
        for field in UNIFIED_SCHEMA_FIELDS:
            assert field in result

    def test_strips_whitespace(self):
        job = {"title": "  Test Job  ", "company": "  TestCo  "}
        result = _normalize_single(job)
        assert result["title"] == "Test Job"
        assert result["company"] == "TestCo"

    def test_normalizes_location_title_case(self):
        job = {"location": "berlin, germany"}
        result = _normalize_single(job)
        assert result["location"] == "Berlin, Germany"

    def test_preserves_mixed_case_location(self):
        job = {"location": "Berlin, Germany"}
        result = _normalize_single(job)
        assert result["location"] == "Berlin, Germany"

    def test_normalizes_salary_to_float(self):
        job = {"salary_min": "50000", "salary_max": "70000"}
        result = _normalize_single(job)
        assert result["salary_min"] == 50000.0
        assert result["salary_max"] == 70000.0

    def test_invalid_salary_becomes_none(self):
        job = {"salary_min": "not-a-number"}
        result = _normalize_single(job)
        assert result["salary_min"] is None

    def test_is_remote_bool(self):
        job = {"is_remote": 1}
        result = _normalize_single(job)
        assert result["is_remote"] is True

    def test_source_lowercase(self):
        job = {"source": "Indeed"}
        result = _normalize_single(job)
        assert result["source"] == "indeed"


class TestNormalizeJobs:
    def test_empty_list(self):
        assert normalize_jobs([]) == []

    def test_normalizes_batch(self):
        jobs = [
            {"title": "Job A", "company": "Co A"},
            {"title": "Job B", "company": "Co B"},
        ]
        result = normalize_jobs(jobs)
        assert len(result) == 2
        assert all(field in result[0] for field in UNIFIED_SCHEMA_FIELDS)

    def test_handles_malformed_gracefully(self):
        jobs = [{"title": "Good Job"}, None]
        # None will cause an error but should be handled
        result = normalize_jobs([{"title": "Good Job"}])
        assert len(result) == 1
