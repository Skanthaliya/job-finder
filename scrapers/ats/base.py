"""
scrapers/ats/base.py — Abstract base class for all ATS scrapers.

Every ATS-specific scraper (Greenhouse, Lever, Workday, etc.) must inherit
from BaseATSScraper and implement the scrape_job() and scrape_company() methods.
"""

from abc import ABC, abstractmethod
import logging
import random

import requests

from config import USER_AGENTS, REQUEST_TIMEOUT, MAX_RETRIES

logger = logging.getLogger(__name__)


class BaseATSScraper(ABC):
    """Abstract base class that all ATS scrapers must inherit from."""

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json, text/html, */*",
            "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
        })
        self.timeout = REQUEST_TIMEOUT
        self.max_retries = MAX_RETRIES

    def _get(self, url: str, params: dict | None = None, headers: dict | None = None) -> requests.Response | None:
        """
        Perform a GET request with retries, timeout, and User-Agent rotation.

        Returns the Response object on success, or None on failure.
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                self.session.headers["User-Agent"] = random.choice(USER_AGENTS)
                if headers:
                    resp = self.session.get(url, params=params, timeout=self.timeout, headers=headers)
                else:
                    resp = self.session.get(url, params=params, timeout=self.timeout)
                resp.raise_for_status()
                return resp
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response is not None else "unknown"
                logger.warning(
                    "[%s] HTTP %s on attempt %d/%d for %s",
                    self.__class__.__name__, status, attempt, self.max_retries, url,
                )
                if status == 429:
                    logger.warning("Rate limited. Waiting 30 seconds...")
                    import time
                    time.sleep(30)
            except requests.exceptions.RequestException as e:
                logger.warning(
                    "[%s] Request error on attempt %d/%d for %s: %s",
                    self.__class__.__name__, attempt, self.max_retries, url, e,
                )
        logger.error("[%s] All %d attempts failed for %s", self.__class__.__name__, self.max_retries, url)
        return None

    def _post(self, url: str, json_data: dict | None = None, headers: dict | None = None) -> requests.Response | None:
        """
        Perform a POST request with retries, timeout, and User-Agent rotation.

        Returns the Response object on success, or None on failure.
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                self.session.headers["User-Agent"] = random.choice(USER_AGENTS)
                resp = self.session.post(url, json=json_data, timeout=self.timeout, headers=headers)
                resp.raise_for_status()
                return resp
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response is not None else "unknown"
                logger.warning(
                    "[%s] HTTP %s on POST attempt %d/%d for %s",
                    self.__class__.__name__, status, attempt, self.max_retries, url,
                )
                if status == 429:
                    import time
                    time.sleep(30)
            except requests.exceptions.RequestException as e:
                logger.warning(
                    "[%s] POST error on attempt %d/%d for %s: %s",
                    self.__class__.__name__, attempt, self.max_retries, url, e,
                )
        logger.error("[%s] All %d POST attempts failed for %s", self.__class__.__name__, self.max_retries, url)
        return None

    @staticmethod
    def _empty_job() -> dict:
        """Return an empty job dict matching the unified schema with all fields set to None."""
        return {
            "source": None,
            "ats_platform": None,
            "title": None,
            "company": None,
            "location": None,
            "country": None,
            "date_posted": None,
            "job_type": None,
            "experience_level": None,
            "is_remote": None,
            "salary_min": None,
            "salary_max": None,
            "salary_currency": None,
            "salary_interval": None,
            "job_url": None,
            "company_url": None,
            "description": None,
            "language": None,
            "ai_score": None,
            "ai_reasoning": None,
            "ai_cover_letter": None,
            "ai_resume_bullets": None,
        }

    @abstractmethod
    def scrape_job(self, url: str) -> dict | None:
        """
        Scrape a single job from URL.

        Returns a dict matching the unified schema, or None on failure.
        """
        pass

    @abstractmethod
    def scrape_company(self, company_slug: str, search_term: str | None = None, location: str | None = None) -> list[dict]:
        """
        Scrape all jobs for a company, optionally filtered by search_term and location.

        Returns a list of dicts matching the unified schema.
        """
        pass
