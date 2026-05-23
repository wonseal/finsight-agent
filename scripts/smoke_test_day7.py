"""Day 7 smoke test: full pipeline including event attribution and risk scoring.

Usage:
    python scripts/smoke_test_day7.py
    python scripts/smoke_test_day7.py AAPL
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import openai
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

from src.sec.client import SECClient
from src.sec.cik_mapper import CIKMapper
from src.sec.companyfacts import CompanyFactsService
from src.sec.submissions import SubmissionsService
from src.sec.filing_downloader import FilingDownloader
from src.metrics.financial_metrics import metric_builder
from src.anomaly.detector import detect_all
from src.anomaly.scoring import RiskScorer
from src.events.event_retriever import EventRetriever
from src.llm.event_analyzer import EventAnalyzer

METRICS = [
    "revenue", "gross_profit", "operating_income", "net_income",
    "assets", "liabilities", "operating_cash_flow",
]


def main() -> int:
    ticker = (sys.argv[1] if len(sys.argv) > 1 else "NVDA").upper()

    user_agent = os.getenv("SEC_USER_AGENT", "FinSightAgent honghak0929@gmail.com")
    client = SECClient(user_agent=user_agent)

    # ── Step 1~2: CIK ────────────────────────────────────────────────────────
    cik = CIKMapper(client).ticker_to_cik(ticker)
    company_name = CIKMapper(client).cik_to_company_name(cik)
    print(f"Ticker:  {ticker}")
    print(f"Company: {company_name}\n")

    # ── Step 3~5: metrics → anomalies ────────────────────────────────────────
    anomaly_cache = Path(f"output/{ticker}_anomalies.csv")
    if anomaly_cache.exists():
        anomalies = pd.read_csv(anomaly_cache)
        print(f"Loaded anomalies from cache: {anomaly_cache}\n")
    else:
        companyfacts = CompanyFactsService(client).get_companyfacts(cik)
        df = metric_builder().build_all(companyfacts, metric_names=METRICS)
        if df.empty:
            print("No metrics data found.")
            return 1
        anomalies = detect_all(df)

    if anomalies.empty:
        print("No anomalies detected.")
        return 1

    # ── Step 6: select top high/medium severity anomaly ──────────────────────
    priority = anomalies[anomalies["severity"].isin(["high", "medium"])]
    if priority.empty:
        priority = anomalies
    top_anomaly = priority.iloc[0].to_dict()

    print("Selected anomaly:")
    print(f"  period:       {top_anomaly['period']}")
    print(f"  metric:       {top_anomaly['metric']}")
    print(f"  severity:     {top_anomaly['severity']}")
    print(f"  anomaly_type: {top_anomaly['anomaly_type']}\n")

    # ── Step 7~8: candidate filings ──────────────────────────────────────────
    submissions = SubmissionsService(client).get_submissions(cik)
    filings_df = SubmissionsService(client).recent_filings_to_df(submissions)
    event_df = SubmissionsService(client).filter_event_filings(filings_df)
    candidates = EventRetriever().find_candidate_filings(event_df, int(top_anomaly["period"]))

    if candidates.empty:
        print("No candidate filings found.")
        return 1

    print("Candidate filings:")
    print(candidates[["form", "filingDate", "primaryDocument"]].to_string(index=False))
    print()

    # ── Step 9~11: EventAnalyzer ─────────────────────────────────────────────
    api_key = os.getenv("OPENAI_API_KEY")
    openai_client = openai.OpenAI(api_key=api_key) if api_key else None
    downloader = FilingDownloader(client)
    analyzer = EventAnalyzer(openai_client, downloader)

    attribution = analyzer.find_best_attribution(candidates, cik, top_anomaly)

    print("Event attribution:")
    print(f"  event_found:  {attribution.event_found}")
    print(f"  event_type:   {attribution.event_type}")
    print(f"  confidence:   {attribution.confidence:.2f}")
    print(f"  explanation:  {attribution.explanation}\n")

    # ── Step 12~13: RiskScorer ───────────────────────────────────────────────
    scored = RiskScorer().score_anomaly(top_anomaly, attribution)

    print("Risk summary:")
    print(f"  score:  {scored['score']}")
    print(f"  status: {scored['status']}")
    print(f"  reason: {scored['reason']}")

    print("\nDay 7 smoke test OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
