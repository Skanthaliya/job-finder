"""Tests for ai/scorer.py — JSON response parsing from Gemini output."""

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai.scorer import _parse_json_response


class TestParseJsonResponse:
    def test_clean_json(self):
        text = '{"score": 75, "reasoning": "Good match", "pros": ["Skills"], "cons": ["Location"]}'
        result = _parse_json_response(text)
        assert result["score"] == 75
        assert result["reasoning"] == "Good match"

    def test_json_with_markdown_fences(self):
        text = '```json\n{"score": 80, "reasoning": "Great", "pros": [], "cons": []}\n```'
        result = _parse_json_response(text)
        assert result["score"] == 80

    def test_json_with_plain_fences(self):
        text = '```\n{"score": 60, "reasoning": "OK", "pros": [], "cons": []}\n```'
        result = _parse_json_response(text)
        assert result["score"] == 60

    def test_json_with_preamble(self):
        text = 'Here is the score:\n{"score": 55, "reasoning": "Decent", "pros": [], "cons": []}'
        result = _parse_json_response(text)
        assert result["score"] == 55

    def test_json_array(self):
        text = '[{"job_index": 0, "score": 70}, {"job_index": 1, "score": 40}]'
        result = _parse_json_response(text)
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["score"] == 70

    def test_json_array_with_fences(self):
        text = '```json\n[{"job_index": 0, "score": 90}]\n```'
        result = _parse_json_response(text)
        assert isinstance(result, list)
        assert result[0]["score"] == 90

    def test_empty_string(self):
        result = _parse_json_response("")
        assert result is None

    def test_invalid_json(self):
        result = _parse_json_response("This is not JSON at all")
        assert result is None

    def test_partial_json(self):
        result = _parse_json_response('{"score": 50, "reasoning": "incomplete')
        assert result is None

    def test_json_with_trailing_text(self):
        text = '{"score": 85, "reasoning": "Excellent", "pros": ["A"], "cons": ["B"]}\n\nLet me know if you need more.'
        result = _parse_json_response(text)
        assert result["score"] == 85

    def test_whitespace_around(self):
        text = '  \n  {"score": 42, "reasoning": "Low", "pros": [], "cons": []}  \n  '
        result = _parse_json_response(text)
        assert result["score"] == 42

    def test_nested_json_in_text(self):
        text = 'Based on analysis: {"score": 65, "reasoning": "Match", "pros": ["skill"], "cons": ["exp"]} end.'
        result = _parse_json_response(text)
        assert result is not None
        assert result["score"] == 65
