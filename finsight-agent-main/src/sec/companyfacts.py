"""Fetch all XBRL company facts for a CIK from SEC EDGAR.

Endpoint shape:
    https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json

Response structure (abbreviated):
    {
      "cik": int,
      "entityName": str,
      "facts": {
        "us-gaap": {
          "Revenues": {
            "label": "...",
            "description": "...",
            "units": {
              "USD": [
                {"val": ..., "fy": ..., "fp": "FY|Q1|Q2|Q3",
                 "form": "10-K|10-Q", "filed": "YYYY-MM-DD",
                 "start": "...", "end": "...", "frame": "...", "accn": "..."},
                ...
              ]
            }
          },
          ...
        },
        "dei": { ... }
      }
    }
"""

from __future__ import annotations

"""
Basic usage:

1. Create a CompanyFactsService object
2. Store the SECClient and cache folder path
3. Call get_companyfacts(cik)
4. Create the file path for the cached JSON file
5. If use_cache=True and the cache file already exists:
    - Read the file
    - Convert the JSON string into a Python dict
    - Return the dict
6. If the cache file does not exist:
    - Create the SEC companyfacts URL
    - Send a request to the SEC API using SECClient
    - Receive the response JSON as a Python dict
    - Create the cache folder if necessary
    - Save the JSON data to a file
    - Return the dict
"""

import json
from pathlib import Path

from src.sec.client import SECClient


class CompanyFactsService:
    """Retrieve and (optionally) cache the full companyfacts JSON for a company."""

    def __init__(
        self,
        client: SECClient,
        cache_dir: str | Path = "data/cache/companyfacts",
    ) -> None:
        self.client = client
        self.cache_dir = Path(cache_dir)

    def companyfacts_url(self, cik: str) -> str:
        return f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

    def get_companyfacts(self, cik: str, use_cache: bool = True) -> dict:
        """Return the full companyfacts JSON for ``cik``.

        ``cik`` must be a 10-digit zero-padded string (use :class:`CIKMapper`).
        Results are cached as ``{cache_dir}/CIK{cik}.json`` on disk.
        """
        cache_file = self.cache_dir / f"CIK{cik}.json"

        if use_cache and cache_file.exists(): # If cache file exists and use_cache is True, load from cache instead of making an API call.
            return json.loads(cache_file.read_text(encoding="utf-8"))

        data = self.client.get_json(self.companyfacts_url(cik))

        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(
            json.dumps(data, indent=2),
            encoding="utf-8",
        )
        return data
