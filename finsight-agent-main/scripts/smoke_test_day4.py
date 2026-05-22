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
from src.metrics.financial_metrics import metric_builder
# Same as streamlit_app.py. In a real project, we would refactor to avoid this duplication.
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


# ── UI ──────────────────────────────────────────────────────────────────────

st.title("FinSight Agent")
st.caption("Financial metrics analysis based on SEC EDGAR filings")

ticker_input = st.text_input("Ticker", value="NVDA", placeholder="e.g. AAPL, MSFT, NVDA")
analyze = st.button("Analyze")

# ── Run analysis ────────────────────────────────────────────────────────────

if analyze and ticker_input:
    ticker = ticker_input.strip().upper()

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

    st.write(f"**{company_name}** (`{ticker}` · CIK: {cik})")
    st.write(f"{df.shape[0]} rows × {df.shape[1]} columns")

    # ── display_df: formatted for display only (df kept as numeric) ──────────
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

    # ── Charts ───────────────────────────────────────────────────────────────

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

    # ── AI Financial Analysis (OpenAI streaming) ─────────────────────────────

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
        st.stop()

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
            st.write_stream(stream_response())
    except Exception as e:
        st.error(f"GPT error: {e}")
