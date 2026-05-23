"""Day 1 smoke test: fetch a ticker's CIK + companyfacts and print a summary.

Usage:
    python scripts/smoke_test_day1.py            # defaults to NVDA
    python scripts/smoke_test_day1.py AAPL
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


REVENUE_TAGS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
]


def _format_billions(value: float | int | None) -> str:
    if value is None:
        return "<no value>"
    return f"${value / 1_000_000_000:,.2f}B"


def main() -> int:
    ticker = (sys.argv[1] if len(sys.argv) > 1 else "NVDA").upper()

    user_agent = os.getenv("SEC_USER_AGENT")

    if user_agent is None:
        user_agent = "FinSightAgent honghak0929@gmail.com"

    client = SECClient(user_agent=user_agent) # SEC requires a user agent with contact info. Set SEC_USER_AGENT env var to override the default.

    # 1. Ticker → CIK
    cik_mapper = CIKMapper(client)
    cik = cik_mapper.ticker_to_cik(ticker) # CIK is a 10-digit zero-padded string, e.g. "0000320193"
    name = cik_mapper.cik_to_company_name(cik) # Company name from SEC records, e.g. "APPLE INC." Note: this may differ from the common name used in the market. For example, "MICROSOFT CORP" vs "Microsoft Corporation".
    print(f"Ticker:  {ticker}")
    print(f"Company: {name}")
    print(f"CIK:     {cik}")
    print()

    # 2. CIK → companyfacts
    facts_svc = CompanyFactsService(client)
    cf = facts_svc.get_companyfacts(cik)

    taxonomies = list(cf.get("facts", {}).keys())
    us_gaap = cf.get("facts", {}).get("us-gaap", {})
    print(f"Taxonomies available: {taxonomies}")
    print(f"us-gaap concepts:     {len(us_gaap)}")

    # 3. Pull the most recent 5 annual revenue records.
    for tag in REVENUE_TAGS:
        if tag not in us_gaap:
            continue

        records = us_gaap[tag].get("units", {}).get("USD", [])
        annual = [r for r in records if r.get("form") == "10-K" and r.get("fp") == "FY"]

        # Same fiscal year may appear in multiple filings (amendments) — keep the
        # latest filed entry for each fy.
        latest_by_fy: dict[int, dict] = {}
        for r in annual:
            fy = r.get("fy")
            if fy is None:
                continue
            cur = latest_by_fy.get(fy)
            if cur is None or r.get("filed", "") > cur.get("filed", ""):
                latest_by_fy[fy] = r

        print(f"\nRevenue tag: {tag}")
        print(f"  {len(records)} total USD records, {len(latest_by_fy)} distinct fiscal years")
        print("  Last 5 annual revenue values:")
        for fy in sorted(latest_by_fy)[-5:]:
            r = latest_by_fy[fy]
            print(
                f"    FY{fy:<5} end={r.get('end')}  filed={r.get('filed')}  "
                f"value={_format_billions(r.get('val'))}"
            )
        break
    else:
        print("\nWARNING: No standard revenue tag found in us-gaap facts.")
        return 1

    print("\nDay 1 smoke test OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
