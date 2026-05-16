from __future__ import annotations

import pandas as pd


class EventRetriever:

    def find_candidate_filings(self, filings_df: pd.DataFrame, anomaly_year: int) -> pd.DataFrame:
        """Return candidate filings filed around the given anomaly year.

        For a FY2024 anomaly, searches filings from 2024-01-01 to 2025-06-30.
        The window extends to June of the following year because annual 10-K filings
        are typically submitted several months after fiscal year end.
        """
        if filings_df.empty:
            return filings_df

        start = pd.Timestamp(year=anomaly_year, month=1, day=1)
        end = pd.Timestamp(year=anomaly_year + 1, month=6, day=30)

        mask = (filings_df["filingDate"] >= start) & (filings_df["filingDate"] <= end)
        return filings_df[mask].reset_index(drop=True)
