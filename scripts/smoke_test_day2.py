"""Day 2 smoke test: extract normalized XBRL facts from SEC companyfacts.

Usage:
    python scripts/smoke_test_day2.py
    python scripts/smoke_test_day2.py AAPL
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Allow running as a script from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.sec.client import SECClient  # noqa: E402
from src.sec.cik_mapper import CIKMapper  # noqa: E402
from src.sec.companyfacts import CompanyFactsService  # noqa: E402
from src.xbrl.fact_extractor import FactExtractor  # noqa: E402


def _format_billions(value: float | int | None) -> str:
    if value is None:
        return "<no value>"
    return f"${value / 1_000_000_000:,.2f}B"


def main() -> int:
    ticker = (sys.argv[1] if len(sys.argv) > 1 else "NVDA").upper()

    user_agent = os.getenv(
        "SEC_USER_AGENT",
        "FinSightAgent honghak0929@gmail.com",
    )

    client = SECClient(user_agent=user_agent)

    cik_mapper = CIKMapper(client)
    cik = cik_mapper.ticker_to_cik(ticker)
    company_name = cik_mapper.cik_to_company_name(cik)

    print(f"Ticker:  {ticker}")
    print(f"Company: {company_name}")
    print(f"CIK:     {cik}")
    print()

    facts_service = CompanyFactsService(client)
    companyfacts = facts_service.get_companyfacts(cik)

    extractor = FactExtractor()
    facts_df = extractor.extract_all_metrics(companyfacts)

    if facts_df.empty:
        print("No facts extracted.")
        return 1

    print("Extracted metrics:")
    summary = (
        facts_df[facts_df["fp"] == "FY"]
        .groupby("metric")
        .size()
        .sort_values(ascending=False)
    )

    for metric, count in summary.items():
        print(f"- {metric}: {count} annual records")

    print("\nAnnual preview:")
    annual_df = facts_df[facts_df["fp"] == "FY"].copy()

    pivot = (
        annual_df.pivot_table(
            index="fy",
            columns="metric",
            values="value",
            aggfunc="last",
        )
        .sort_index()
        .tail(8)
    )

    display_cols = [
        col
        for col in [
            "revenue",
            "gross_profit",
            "operating_income",
            "net_income",
            "assets",
            "liabilities",
            "operating_cash_flow",
        ]
        if col in pivot.columns
    ]

    if not display_cols:
        print("No display columns found.")
        return 1

    preview = pivot[display_cols].copy()

    for col in preview.columns:
        preview[col] = preview[col].apply(_format_billions)

    print(preview)

    print("\nDay 2 smoke test OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())