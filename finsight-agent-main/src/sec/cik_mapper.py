"""Map US ticker symbols to SEC central index keys (CIK).

SEC publishes the full ticker → CIK mapping as a single JSON file. We
cache it locally to avoid re-downloading on every run.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from src.sec.client import SECClient

TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"


class CIKMapper:
    """Resolve ticker → 10-digit zero-padded CIK using SEC's public ticker map."""

    def __init__(
        self,
        client: SECClient,
        cache_path: str | Path = "data/cache/company_tickers.json",
    ) -> None:
        self.client = client
        self.cache_path = Path(cache_path)

    def load_ticker_map(self, force_refresh: bool = False) -> dict:
        """Load the ticker → CIK mapping, fetching from SEC on first use."""
        if self.cache_path.exists() and not force_refresh:
            return json.loads(self.cache_path.read_text(encoding="utf-8"))

        data = self.client.get_json(TICKER_MAP_URL)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(data, indent=2),
            encoding="utf-8",
        )
        return data

    def ticker_to_cik(self, ticker: str) -> str:
        """Return the 10-digit zero-padded CIK for ``ticker``.

        Raises
        ------
        ValueError
            If the ticker is not present in SEC's ticker map.
        """
        ticker = ticker.strip().upper()
        data = self.load_ticker_map()
        for entry in data.values():
            if entry.get("ticker", "").upper() == ticker:
                return str(entry["cik_str"]).zfill(10)
        raise ValueError(f"Ticker not found in SEC ticker map: {ticker}")

    def cik_to_company_name(self, cik: str) -> Optional[str]:
        """Return the registrant name for a given CIK, if known."""
        cik_int = int(cik)
        data = self.load_ticker_map()
        for entry in data.values():
            if entry.get("cik_str") == cik_int:
                return entry.get("title")
        return None
