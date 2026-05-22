"""Day 6 smoke test: filing retrieval and parsing pipeline.

Usage:
    python scripts/smoke_test_day6.py
    python scripts/smoke_test_day6.py AAPL
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.sec.client import SECClient
from src.sec.cik_mapper import CIKMapper
from src.sec.companyfacts import CompanyFactsService
from src.sec.submissions import SubmissionsService
from src.sec.filing_downloader import FilingDownloader
from src.metrics.financial_metrics import metric_builder
from src.anomaly.detector import detect_all
from src.events.event_retriever import EventRetriever
from src.events.filling_parser import FilingParser

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
    if not companyfacts:
        print("No company facts found.")
        return 1
    anomaly_cache = Path(f"output/{ticker}_anomalies.csv")
    if anomaly_cache.exists():
        import pandas as pd
        anomalies = pd.read_csv(anomaly_cache)
        print(f"Loaded anomalies from cache: {anomaly_cache}\n")
    else:
        df = metric_builder().build_all(companyfacts, metric_names=METRICS)
        if df.empty:
            print("No metrics data found.")
            return 1
        anomalies = detect_all(df)

    if anomalies.empty:
        print("No anomalies detected.")
        return 1
    # Step 7. select first anomaly
    first_anomaly = anomalies.iloc[0]
    anomaly_year = int(first_anomaly["period"])
    print("First anomaly:")
    print(first_anomaly.to_string())
    print()
    filing_parser = FilingParser()
    downloader = FilingDownloader(client)

    # Step 8. submissions → filings → candidate search
    submissions = SubmissionsService(client).get_submissions(cik)
    filings = SubmissionsService(client).recent_filings_to_df(submissions)
    filtered_filings = SubmissionsService(client).filter_event_filings(filings)
    if filtered_filings.empty:
        print("No event filings found.")
        return 1
    candidates_filings = EventRetriever().find_candidate_filings(filtered_filings, anomaly_year)
    # Step 9. download first candidate filing
    if candidates_filings.empty:
        print("No candidate filings found for the anomaly year.")
        return 1
    row = candidates_filings.iloc[0]
    print(f"Downloading: {row['form']} {row['filingDate'].date()}\n")
    html = downloader.download_primary_document(cik, row["accessionNumber"], row["primaryDocument"])
        
    # Step 10. convert HTML → plain text
    plaint_text = filing_parser.html_to_text(html)

    # Step 11. print relevant excerpts (up to 30 lines)
    excerpts = filing_parser.extract_relevant_sections(plaint_text)
    print("Relevant excerpts:")
    for line in excerpts.splitlines()[:30]:
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
