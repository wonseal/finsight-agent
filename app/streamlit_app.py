from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import openai
import streamlit as st
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
    "revenue",
    "gross_profit",
    "operating_income",
    "net_income",
    "assets",
    "liabilities",
    "operating_cash_flow",
]


@st.cache_data(show_spinner=False)
def load_company_metrics(ticker: str) -> tuple[str, str, object]:
    """Fetch SEC data and compute metrics. Results are cached per ticker."""
    user_agent = os.getenv("SEC_USER_AGENT", "FinSightAgent honghak0929@gmail.com")
    client = SECClient(user_agent=user_agent)

    cik = CIKMapper(client).ticker_to_cik(ticker)
    company_name = CIKMapper(client).cik_to_company_name(cik)
    companyfacts = CompanyFactsService(client).get_companyfacts(cik)

    df = metric_builder().build_all(companyfacts, metric_names=METRICS)
    return cik, company_name, df


# ── UI ───────────────────────────────────────────────────────────────────────

st.title("FinSight Agent")
st.caption("Financial metrics analysis based on SEC EDGAR filings")

ticker_input = st.text_input("Ticker", value="NVDA", placeholder="e.g. AAPL, MSFT, NVDA")
analyze = st.button("Analyze")

# ── Load data on Analyze click, persist to session_state ────────────────────

if analyze and ticker_input:
    ticker = ticker_input.strip().upper()

    # Clear previous results if ticker changed (but keep if same ticker to allow re-analysis without re-fetching)
    if st.session_state.get("result", {}).get("ticker") != ticker:
        st.session_state.pop("ai_analysis", None)
        st.session_state.pop("attribution_result", None)

    with st.spinner(f"Loading {ticker} data..."):
        try:
            cik, company_name, df = load_company_metrics(ticker)
        except ValueError:
            st.error(f"Ticker **{ticker}** not found. Please check if it is a valid SEC-registered ticker.")
            st.stop()
        except Exception as e:
            if hasattr(e, "response") and e.response is not None:
                st.error(f"SEC API error (HTTP {e.response.status_code}). Please try again later.")
            else:
                st.error(f"Error: {e}")
            st.stop()

    if df.empty:
        st.warning("No data found.")
        st.stop()

    st.session_state["result"] = {
        "cik": cik,
        "company_name": company_name,
        "df": df,
        "ticker": ticker,
    }

# ── Display results from session_state (survives button re-renders) ──────────

if "result" not in st.session_state:
    st.stop()

cik = st.session_state["result"]["cik"]
company_name = st.session_state["result"]["company_name"]
df = st.session_state["result"]["df"]
ticker = st.session_state["result"]["ticker"]

st.write(f"**{company_name}** (`{ticker}` · CIK: {cik})")
st.write(f"{df.shape[0]} rows x {df.shape[1]} columns")

# ── Formatting helpers (display only — df kept as numeric) ───────────────────

def _fmt_dollar(v):
    if v is None or (isinstance(v, float) and v != v):
        return "N/A"
    return f"${v / 1_000_000_000:,.2f}B"

def _fmt_pct_col(v):
    if v is None or (isinstance(v, float) and v != v):
        return "N/A"
    return f"{v:+.1f}%"

def _fmt_ratio_col(v):
    if v is None or (isinstance(v, float) and v != v):
        return "N/A"
    return f"{v:.2f}x"

DOLLAR_COLS = [c for c in METRICS if c in df.columns]
PCT_COLS = [c for c in df.columns if c.endswith("_YoY")] + [
    c for c in ["gross_margin", "operating_margin", "net_margin", "ROA", "ROE"] if c in df.columns
]
RATIO_COLS = [
    c for c in [
        "liabilities_to_equity", "liabilities_to_assets", "debt_to_equity",
        "current_ratio", "quick_ratio", "ocf_to_net_income",
        "fcf_to_net_income", "fcf_to_revenue",
    ] if c in df.columns
]

display_df = df.copy()
for col in DOLLAR_COLS:
    display_df[col] = display_df[col].apply(_fmt_dollar)
for col in PCT_COLS:
    display_df[col] = display_df[col].apply(_fmt_pct_col)
for col in RATIO_COLS:
    display_df[col] = display_df[col].apply(_fmt_ratio_col)

st.dataframe(display_df, use_container_width=True)

# ── Charts ────────────────────────────────────────────────────────────────────

import plotly.express as px

st.divider()
st.subheader("Financial Charts")

annual_df = df[df["fp"] == "FY"].sort_values("fy").copy()

col1, col2 = st.columns(2)

with col1:
    if "revenue" in annual_df.columns:
        fig = px.bar(
            annual_df,
            x="fy",
            y="revenue",
            title="Revenue Trend",
            labels={"fy": "Fiscal Year", "revenue": "Revenue (USD)"},
        )
        fig.update_traces(marker_color="#4C78A8")
        fig.update_layout(yaxis_tickformat=".2s")
        st.plotly_chart(fig, use_container_width=True)

with col2:
    if "revenue_YoY" in annual_df.columns:
        fig = px.bar(
            annual_df.dropna(subset=["revenue_YoY"]),
            x="fy",
            y="revenue_YoY",
            title="Revenue Growth (YoY %)",
            labels={"fy": "Fiscal Year", "revenue_YoY": "Growth (%)"},
            color="revenue_YoY",
            color_continuous_scale=["#d62728", "#aec7e8", "#2ca02c"],
            color_continuous_midpoint=0,
        )
        fig.update_layout(coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)

col3, col4 = st.columns(2)

with col3:
    margin_cols = [c for c in ["gross_margin", "operating_margin", "net_margin"] if c in annual_df.columns]
    if margin_cols:
        fig = px.line(
            annual_df,
            x="fy",
            y=margin_cols,
            title="Profitability Margins (%)",
            labels={"fy": "Fiscal Year", "value": "%", "variable": "Metric"},
            markers=True,
        )
        st.plotly_chart(fig, use_container_width=True)

with col4:
    if "liabilities_to_assets" in annual_df.columns:
        fig = px.line(
            annual_df.dropna(subset=["liabilities_to_assets"]),
            x="fy",
            y="liabilities_to_assets",
            title="Balance Sheet Risk (Liabilities / Assets)",
            labels={"fy": "Fiscal Year", "liabilities_to_assets": "Ratio"},
            markers=True,
        )
        fig.update_traces(line_color="#d62728")
        fig.add_hline(y=0.5, line_dash="dash", line_color="gray", annotation_text="50%")
        st.plotly_chart(fig, use_container_width=True)

# ── AI Financial Analysis (OpenAI streaming) ─────────────────────────────────

st.divider()
st.subheader("AI Financial Analysis")

annual_df = annual_df.tail(10)

def _fmt(v):
    if v is None or (isinstance(v, float) and v != v):
        return "N/A"
    return f"${v / 1_000_000_000:,.2f}B"

def _fmt_pct(v):
    if v is None or (isinstance(v, float) and v != v):
        return "N/A"
    return f"{v:+.1f}%"

summary_lines = []
for _, row in annual_df.iterrows():
    fy = int(row["fy"]) if "fy" in row and row["fy"] == row["fy"] else "?"
    rev = _fmt(row.get("revenue"))
    ni = _fmt(row.get("net_income"))
    ocf = _fmt(row.get("operating_cash_flow"))
    gm = _fmt_pct(row.get("gross_margin"))
    nm = _fmt_pct(row.get("net_margin"))
    rev_yoy = _fmt_pct(row.get("revenue_YoY"))
    ni_yoy = _fmt_pct(row.get("net_income_YoY"))
    summary_lines.append(
        f"FY{fy}: Revenue={rev} ({rev_yoy} YoY), Net Income={ni} ({ni_yoy} YoY), "
        f"OCF={ocf}, Gross Margin={gm}, Net Margin={nm}"
    )

financial_summary = "\n".join(summary_lines)

prompt = f"""You are a financial analyst. Analyze the following financial data for {company_name} ({ticker}) and provide key insights.

Recent 5-Year Financial Summary:
{financial_summary}

Please provide:
1. Revenue trend and growth analysis
2. Profitability assessment (margins, net income trend)
3. Cash flow health
4. Key strengths and risks
5. Brief outlook

Be concise and data-driven. Use the actual numbers from the data."""

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.warning("OPENAI_API_KEY is not set. Skipping AI analysis.")
else:
    if "ai_analysis" not in st.session_state:
        openai_client = openai.OpenAI(api_key=api_key)

        def stream_response():
            stream = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                stream=True,
            )
            for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield content

        try:
            with st.spinner("Analyzing with GPT..."):
                full_response = st.write_stream(stream_response())
                st.session_state["ai_analysis"] = full_response
        except Exception as e:
            st.error(f"GPT error: {e}")
    else:
        st.write(st.session_state["ai_analysis"])

# ── Event Attribution ─────────────────────────────────────────────────────────

st.divider()
st.subheader("Event Attribution")

if not os.getenv("OPENAI_API_KEY"):
    st.info("Event Attribution requires an OpenAI API key (not configured in this deployment).")

elif st.button("Analyze Event Attribution for Top Anomaly"):
    with st.spinner("Detecting anomalies..."):
        sec_client = SECClient(user_agent=os.getenv("SEC_USER_AGENT", "FinSightAgent honghak0929@gmail.com"))
        submissions = SubmissionsService(sec_client).get_submissions(cik)
        sic_code = submissions.get("sic")
        anomalies = detect_all(df, sic_code=sic_code)

    if anomalies.empty:
        st.session_state["attribution_result"] = None
    else:
        priority = anomalies[anomalies["severity"].isin(["high", "medium"])]
        top_anomaly = (priority if not priority.empty else anomalies).iloc[0].to_dict()

        with st.spinner("Searching filings and running LLM analysis..."):
            try:
                filings_df = SubmissionsService(sec_client).recent_filings_to_df(submissions)
                event_df = SubmissionsService(sec_client).filter_event_filings(filings_df)
                candidates = EventRetriever().find_candidate_filings(event_df, int(top_anomaly["period"]))

                openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                downloader = FilingDownloader(sec_client)
                analyzer = EventAnalyzer(openai_client, downloader)
                attribution = analyzer.find_best_attribution(candidates, cik, top_anomaly)
                scored = RiskScorer().score_anomaly(top_anomaly, attribution)

                st.session_state["attribution_result"] = {
                    "top_anomaly": top_anomaly,
                    "attribution": attribution,
                    "scored": scored,
                }
            except Exception as e:
                st.error(f"Attribution error: {e}")


if "attribution_result" in st.session_state:
    res = st.session_state["attribution_result"]
    
    if res is None:
        st.info("No anomalies detected.")
    else:
        top_anomaly = res["top_anomaly"]
        attribution = res["attribution"]
        scored = res["scored"]

        st.markdown("**Selected Anomaly**")
        col_a, col_b, col_c, col_d = st.columns(4)
        col_a.metric("Period", top_anomaly["period"])
        col_b.metric("Metric", top_anomaly["metric"])
        col_c.metric("Severity", top_anomaly["severity"])
        col_d.metric("Type", top_anomaly["anomaly_type"])

        st.markdown("**Event Attribution**")
        found_label = "Explained" if attribution.event_found else "Unexplained"
        col_e1, col_e2, col_e3 = st.columns(3)
        col_e1.metric("Result", found_label)
        col_e2.metric("Event Type", attribution.event_type)
        col_e3.metric("Confidence", f"{attribution.confidence:.0%}")
        st.info(attribution.explanation)

        st.markdown("**Review Priority**")
        status_color = {"high_review_priority": "🔴", "medium_review_priority": "🟡", "low_review_priority": "🟢"}
        icon = status_color.get(scored["status"], "⚪")
        col_s1, col_s2 = st.columns(2)
        col_s1.metric("Score", scored["score"])
        col_s2.metric("Status", f"{icon} {scored['status']}")
        st.caption(scored["reason"])