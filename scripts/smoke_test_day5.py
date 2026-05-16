"""Day 5 smoke test: anomaly detection pipeline.

Usage:
    python scripts/smoke_test_day5.py
    python scripts/smoke_test_day5.py AAPL
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
from src.anomaly.detector import detect_all

METRICS = [
    "revenue",
    "gross_profit",
    "operating_income",
    "net_income",
    "assets",
    "liabilities",
    "operating_cash_flow",
]


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

    df = metric_builder().build_all(companyfacts, metric_names=METRICS)
    if df.empty:
        print("No metrics data found.")
        return 1

    print(f"Metrics shape: {df.shape}\n")

    anomalies = detect_all(df)

    if anomalies.empty:
        print("No anomalies detected.")
    else:
        print(f"Detected {len(anomalies)} anomalies:\n")
        print(anomalies.to_string(index=False))

    out_path = Path(f"output/{ticker}_anomalies.csv")
    out_path.parent.mkdir(exist_ok=True)
    anomalies.to_csv(out_path, index=False)
    print(f"\nSaved: {out_path}")
    print("\nDay 5 smoke test OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
