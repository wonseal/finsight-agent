"""SEC EDGAR HTTP client with rate limiting and required User-Agent header.

SEC enforces a fair-access policy of 10 requests/second and requires a
descriptive User-Agent on every request. See:
https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data
"""
from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlparse

import requests


class SECClient:
    """Thin HTTP client for SEC EDGAR APIs.

    Parameters
    ----------
    user_agent:
        Descriptive User-Agent string. SEC expects something like
        ``"FinSightAgent your-email@example.com"``. Requests without a
        proper User-Agent are blocked.
    request_interval:
        Minimum seconds between requests. Default 0.15s keeps us safely
        under SEC's 10 req/sec ceiling.
    timeout:
        Per-request timeout in seconds.
    """

    def __init__(
        self,
        user_agent: str,
        request_interval: float = 0.15,
        timeout: float = 30.0,
    ) -> None:
        if not user_agent or "@" not in user_agent:
            raise ValueError(
                "SEC requires a User-Agent in the form 'AppName your@email.com'. "
                "Set SEC_USER_AGENT in your .env file."
            )
        self.user_agent = user_agent
        self.request_interval = request_interval
        self.timeout = timeout
        self._last_request_time = 0.0 #initialize to epoch start so the first request is not delayed

    def _wait(self) -> None:
        elapsed = time.time() - self._last_request_time # Seconds since last request
        if elapsed < self.request_interval:
            time.sleep(self.request_interval - elapsed)
        self._last_request_time = time.time()

    def _headers_for(self, url: str) -> dict[str, str]:
        host = urlparse(url).netloc
        return {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate", # SEC supports compressed responses, which can speed up large filings
            "Host": host,
        }

    def get_json(self, url: str) -> dict[str, Any]:
        """GET a URL and decode the JSON body."""
        self._wait()
        resp = requests.get(url, headers=self._headers_for(url), timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def get_text(self, url: str) -> str:
        """GET a URL and return the raw text body (used for filing HTML)."""
        self._wait()
        resp = requests.get(url, headers=self._headers_for(url), timeout=self.timeout)
        resp.raise_for_status()
        return resp.text
