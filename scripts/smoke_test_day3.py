"""Day 3 smoke test: build wide-format metric table via metric_builder.

Usage:
    python scripts/smoke_test_day3.py
    python scripts/smoke_test_day3.py AAPL
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.sec.client import SECClient
from src.sec.cik_mapper import CIKMapper
from src.sec.companyfacts import CompanyFactsService
from src.metrics.financial_metrics import metric_builder

METRICS = [
    "revenue",
    "gross_profit",
    "operating_income",
    "net_income",
    "assets",
    "liabilities",
    "operating_cash_flow",
]


def _fmt(value: float | None) -> str:
    if value is None or (isinstance(value, float) and value != value):
        return "N/A"
    return f"${value / 1_000_000_000:,.2f}B"


def _fmt_pct(value: float | None) -> str:
    if value is None or (isinstance(value, float) and value != value):
        return "N/A"
    return f"{value:+.1f}%" if value < 0 or value >= 0 else "N/A"


def _fmt_ratio(value: float | None) -> str:
    if value is None or (isinstance(value, float) and value != value):
        return "N/A"
    return f"{value:.2f}x"


def main() -> int:
    ticker = (sys.argv[1] if len(sys.argv) > 1 else "NVDA").upper()

    user_agent = os.getenv("SEC_USER_AGENT", "FinSightAgent honghak0929@gmail.com")
    client = SECClient(user_agent=user_agent)

    cik = CIKMapper(client).ticker_to_cik(ticker)
    company_name = CIKMapper(client).cik_to_company_name(cik)
    print(f"Ticker:  {ticker}")
    print(f"Company: {company_name}")
    print(f"CIK:     {cik}\n")

    companyfacts = CompanyFactsService(client).get_companyfacts(cik)

    builder = metric_builder()
    df = builder.build_all(companyfacts, metric_names=METRICS)

    if df.empty:
        print("No data extracted.")
        return 1

    print(f"Shape: {df.shape}  (rows x cols)\n")
    # preview last 5 annual (FY) periods
    annual = df[df["fp"] == "FY"].sort_values("fy").tail(5).copy()

    preview = annual.copy()

    YOY_COLS = [c for c in preview.columns if c.endswith("_YoY")]
    MARGIN_COLS = ["gross_margin", "operating_margin", "net_margin", "ROA", "ROE"]
    RATIO_COLS = ["liabilities_to_equity", "liabilities_to_assets", "debt_to_equity",
                  "current_ratio", "quick_ratio", "ocf_to_net_income",
                  "fcf_to_net_income", "fcf_to_revenue"]

    for col in METRICS:
        if col in preview.columns:
            preview[col] = preview[col].apply(_fmt)
    for col in YOY_COLS:
        preview[col] = preview[col].apply(_fmt_pct)
    for col in MARGIN_COLS:
        if col in preview.columns:
            preview[col] = preview[col].apply(_fmt_pct)
    for col in RATIO_COLS:
        if col in preview.columns:
            preview[col] = preview[col].apply(_fmt_ratio)

    print("Annual preview (last 5 FY):")
    print(preview.to_string(index=False))

    out_path = Path(f"output/{ticker}_financials.csv")
    out_path.parent.mkdir(exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"\nSaved: {out_path}")
    print("\nDay 3 smoke test OK.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
