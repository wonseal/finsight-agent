from __future__ import annotations

import pandas as pd

from src.sec.client import SECClient

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

EVENT_FORMS = ("8-K", "10-Q", "10-K")


class SubmissionsService:

    def __init__(self, client: SECClient) -> None:
        self.client = client

    def get_submissions(self, cik: str) -> dict:
        """Fetch SEC submissions JSON for the given CIK."""
        url = SUBMISSIONS_URL.format(cik=cik.zfill(10))
        return self.client.get_json(url)

    def recent_filings_to_df(self, submissions: dict) -> pd.DataFrame:
        """Convert the recent filings section of a submissions JSON into a DataFrame."""
        recent = submissions.get("filings", {}).get("recent", {})
        if not recent:
            return pd.DataFrame()

        df = pd.DataFrame({
            "form":            recent.get("form", []),
            "filingDate":      recent.get("filingDate", []),
            "accessionNumber": recent.get("accessionNumber", []),
            "primaryDocument": recent.get("primaryDocument", []),
            "reportDate":      recent.get("reportDate", []),
        })

        df["filingDate"] = pd.to_datetime(df["filingDate"], errors="coerce")
        df["reportDate"] = pd.to_datetime(df["reportDate"], errors="coerce")

        return df.sort_values("filingDate", ascending=False).reset_index(drop=True)

    def filter_event_filings(self, filings_df: pd.DataFrame) -> pd.DataFrame:
        """Filter filings to 8-K, 10-Q, and 10-K only."""
        if filings_df.empty:
            return filings_df
        return filings_df[filings_df["form"].isin(EVENT_FORMS)].reset_index(drop=True)
