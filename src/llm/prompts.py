from __future__ import annotations

SYSTEM_PROMPT = """You are a financial analyst assistant.

Your job is to determine whether a detected financial anomaly can be explained by the provided SEC filing excerpts.

Rules:
1. Do not invent explanations. Use only the provided filing excerpts.
2. If there is no clear match in the excerpts, return event_found=false.
3. Distinguish explained anomaly (event_found=true) from unexplained anomaly (event_found=false).
4. Return structured output only — no free-form commentary outside the JSON.
5. confidence must be between 0.0 and 1.0.
6. If event_found is false, event_type must be "unexplained"."""


USER_PROMPT_TEMPLATE = """Anomaly detected:
- Period: {period}
- Metric: {metric}
- Value: {value}
- Anomaly type: {anomaly_type}
- Severity: {severity}

SEC filing excerpt ({source_form}, filed {source_filing_date}):
\"\"\"
{excerpt}
\"\"\"

Does the filing excerpt explain this anomaly?
Return a JSON object with exactly these fields:
- event_found (bool)
- event_type (must be exactly one of: "demand_growth", "acquisition", "divestiture", "new_product", "price_increase", "cost_reduction", "restructuring", "impairment", "macroeconomic_factor", "accounting_change", "margin_pressure", "cashflow_issue", "debt_increase", "unexplained", "other")
- explanation (str, quote directly from the excerpt if possible)
- source_form (str)
- source_filing_date (str)
- confidence (float, 0.0 to 1.0)"""


def build_user_prompt(
    period: int,
    metric: str,
    value: float,
    anomaly_type: str,
    severity: str,
    source_form: str,
    source_filing_date: str,
    excerpt: str,
) -> str:
    return USER_PROMPT_TEMPLATE.format(
        period=period,
        metric=metric,
        value=value,
        anomaly_type=anomaly_type,
        severity=severity,
        source_form=source_form,
        source_filing_date=source_filing_date,
        excerpt=excerpt,
    )
