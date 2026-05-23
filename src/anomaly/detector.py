from __future__ import annotations

import numpy as np
import pandas as pd

ZSCORE_METRICS = [
    "revenue_YoY",
    "gross_profit_YoY",
    "operating_income_YoY",
    "net_income_YoY",
    "assets_YoY",
    "liabilities_YoY",
    "operating_cash_flow_YoY",
    "gross_margin",
    "operating_margin",
    "net_margin",
    "fcf_to_revenue",
]

COLUMNS = ["period", "metric", "value", "severity", "anomaly_type", "method", "message", "z_score"]

_RULE_MESSAGES = {
    "revenue_drop":                  "Revenue declined more than 20% YoY.",
    "revenue_spike":                 "Revenue grew more than 50% YoY.",
    "high_leverage":                 "Liabilities exceed industry threshold of total assets.",
    "leverage_spike":                "Liabilities-to-assets rose sharply vs. this company's own history.",
    "earnings_cashflow_divergence":  "Net income is positive but operating cash flow is negative.",
    "ocf_quality_issue":             "Operating cash flow is less than 50% of net income.",
    "negative_gross_margin":         "Gross margin is negative — selling below cost.",
    "net_loss":                      "Company reported a net loss.",
    "liquidity_risk":                "Current ratio below 1.0 — short-term liabilities exceed current assets.",
    "margin_collapse":               "Operating margin dropped more than 10 percentage points YoY.",
}

# ── Industry leverage thresholds (A: absolute threshold) ──────────────────────
# Based on SEC SIC codes. Source: industry average leverage ratio benchmarks.
# SIC classification: https://www.osha.gov/data/sic-manual
_LEVERAGE_THRESHOLDS: dict[str, float] = {
    "bank":        0.92,  # SIC 6000-6199: commercial banks
    "insurance":   0.88,  # SIC 6300-6411: insurance
    "real_estate": 0.85,  # SIC 6500-6552: real estate
    "utility":     0.75,  # SIC 4900-4991: utilities
    "default":     0.80,  # all other industries
}


def _leverage_threshold(sic_code: str | None) -> float:
    """Return the industry leverage threshold for the given SIC code."""
    if not sic_code:
        return _LEVERAGE_THRESHOLDS["default"]

    sic = str(sic_code).strip()

    if sic[:2] in ("60", "61"):
        return _LEVERAGE_THRESHOLDS["bank"]
    if sic[:2] in ("63", "64"):
        return _LEVERAGE_THRESHOLDS["insurance"]
    if sic[:2] in ("65",):
        return _LEVERAGE_THRESHOLDS["real_estate"]
    if sic[:2] in ("49",):
        return _LEVERAGE_THRESHOLDS["utility"]

    return _LEVERAGE_THRESHOLDS["default"]


def _expanding_zscore_records(
    annual: pd.DataFrame,
    metric: str,
    min_periods: int = 6,
) -> list[dict]:
    """
    Expanding window Z-score: only prior data is used for mean/std at each
    evaluation point.

    FY2017 evaluation → mean/std computed from FY2016 and earlier only
    FY2018 evaluation → mean/std computed from FY2017 and earlier only

    This fully eliminates look-ahead bias where future data would dilute the
    severity of past anomalies.
    """
    series = annual[["fy", metric]].dropna(subset=[metric]).reset_index(drop=True)

    # Need at least min_periods + 1 points to evaluate even one period
    if len(series) < min_periods + 1:
        return []

    records: list[dict] = []

    for i in range(min_periods, len(series)):
        # Use only data prior to current point (prevents look-ahead bias)
        historical = series[metric].iloc[:i]
        current_val = series[metric].iloc[i]
        current_fy  = series["fy"].iloc[i]

        mean = historical.mean()
        std  = historical.std()

        if std == 0 or np.isnan(std):
            continue

        z = (current_val - mean) / std
        abs_z = abs(z)
        # Only consider as anomaly if abs(z) >= 2.0 (medium or high severity)
        if abs_z < 2.0:
            continue
        # significant anomaly if abs_z >= 2.0, with severity "high" if abs_z >= 3.0
        records.append({
            "period":       int(current_fy),
            "metric":       metric,
            "value":        round(current_val, 4),
            "severity":     "high" if abs_z >= 3.0 else "medium",
            "anomaly_type": "positive_spike" if z > 0 else "negative_spike",
            "method":       "zscore_expanding",
            "message":      (
                f"z={z:+.2f} — deviated from prior {i}-year mean "
                f"(μ={mean:.2f}, σ={std:.2f}). "
                f"Based on FY{int(series['fy'].iloc[0])}–FY{int(series['fy'].iloc[i-1])} only."
            ),
            "z_score":      round(z, 2),
        })

    return records


def detect_zscore_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """Detect anomalies using expanding window Z-score."""
    if "fp" not in df.columns or "fy" not in df.columns:
        return pd.DataFrame(columns=COLUMNS)
    annual = df[df["fp"] == "FY"].dropna(subset=["fy"]).sort_values("fy").copy()
    records: list[dict] = []

    for metric in ZSCORE_METRICS:
        if metric not in annual.columns:
            continue
        records.extend(_expanding_zscore_records(annual, metric))

    if not records:
        return pd.DataFrame(columns=COLUMNS)

    return (
        pd.DataFrame(records)[COLUMNS]
        .sort_values(
            ["period", "z_score"],
            key=lambda s: s.abs() if s.name == "z_score" else s,
            ascending=[False, False],
        )
        .reset_index(drop=True)
    )


# ── Rule-based anomaly detection ──────────────────────────────────────────────

def detect_rule_based_anomalies(
    df: pd.DataFrame,
    sic_code: str | None = None,
) -> pd.DataFrame:
    """
    Rule-based anomaly detection.

    A (absolute threshold): catches outright high leverage using industry benchmarks.
    C (vs. own history): catches sudden leverage spikes using an expanding window.
    """
    if "fp" not in df.columns or "fy" not in df.columns:
        return pd.DataFrame(columns=COLUMNS)
    annual = df[df["fp"] == "FY"].dropna(subset=["fy"]).sort_values("fy").copy().reset_index(drop=True)
    records: list[dict] = []

    # Determine industry threshold (A)
    leverage_threshold = _leverage_threshold(sic_code)

    def _add(fy, metric, value, severity, anomaly_type):
        records.append({
            "period":       int(fy),
            "metric":       metric,
            "value":        round(float(value), 4),
            "severity":     severity,
            "anomaly_type": anomaly_type,
            "method":       "rule",
            "message":      _RULE_MESSAGES.get(anomaly_type, ""),
            "z_score":      float("nan"),
        })

    for _, row in annual.iterrows():
        fy = row["fy"]

        # Revenue YoY
        if "revenue_YoY" in annual.columns and not pd.isna(row.get("revenue_YoY")):
            yoy = row["revenue_YoY"]
            if yoy < -20:
                _add(fy, "revenue_YoY", yoy, "high", "revenue_drop")
            elif yoy > 50:
                _add(fy, "revenue_YoY", yoy, "medium", "revenue_spike")

        # A: detect high-risk leverage against industry absolute threshold
        if "liabilities_to_assets" in annual.columns and not pd.isna(row.get("liabilities_to_assets")):
            if row["liabilities_to_assets"] > leverage_threshold:
                _add(fy, "liabilities_to_assets", row["liabilities_to_assets"], "high", "high_leverage")

        # Earnings / cashflow divergence
        if all(c in annual.columns for c in ["net_income", "operating_cash_flow"]):
            ni  = row.get("net_income")
            ocf = row.get("operating_cash_flow")
            if not (pd.isna(ni) or pd.isna(ocf)):
                if ni > 0 and ocf < 0:
                    _add(fy, "operating_cash_flow", ocf, "high", "earnings_cashflow_divergence")

        # OCF quality (net_income > 0 guard: prevents false positive when both NI and OCF are negative)
        if "ocf_to_net_income" in annual.columns and not pd.isna(row.get("ocf_to_net_income")):
            ni_val = row.get("net_income")
            if not pd.isna(ni_val) and ni_val > 0 and 0 < row["ocf_to_net_income"] < 0.5:
                _add(fy, "ocf_to_net_income", row["ocf_to_net_income"], "medium", "ocf_quality_issue")

        # Negative gross margin
        if "gross_margin" in annual.columns and not pd.isna(row.get("gross_margin")):
            if row["gross_margin"] < 0:
                _add(fy, "gross_margin", row["gross_margin"], "high", "negative_gross_margin")

        # Net loss
        if "net_income" in annual.columns and not pd.isna(row.get("net_income")):
            if row["net_income"] < 0:
                _add(fy, "net_income", row["net_income"], "medium", "net_loss")

        # Liquidity risk
        if "current_ratio" in annual.columns and not pd.isna(row.get("current_ratio")):
            if row["current_ratio"] < 1.0:
                _add(fy, "current_ratio", row["current_ratio"], "high", "liquidity_risk")

    # Margin collapse (diff-based)
    if "operating_margin" in annual.columns:
        margin_diff = annual["operating_margin"].diff()
        for idx, diff_val in margin_diff.items():
            if pd.isna(diff_val):
                continue
            if diff_val < -10:
                _add(annual.loc[idx, "fy"], "operating_margin", annual.loc[idx, "operating_margin"], "high", "margin_collapse")

    # C: detect sudden leverage spike vs. own history (expanding window)
    if "liabilities_to_assets" in annual.columns:
        lev_records = _expanding_zscore_records(annual, "liabilities_to_assets", min_periods=6)
        for r in lev_records:
            # only positive_spike — a sudden rise in leverage is the risk
            if r["anomaly_type"] == "positive_spike":
                records.append({
                    **r,
                    "anomaly_type": "leverage_spike",
                    "method":       "rule_expanding",
                    "message":      _RULE_MESSAGES["leverage_spike"],
                })

    if not records:
        return pd.DataFrame(columns=COLUMNS)

    return (
        pd.DataFrame(records)[COLUMNS]
        .sort_values(["period", "severity"], ascending=[False, True])
        .reset_index(drop=True)
    )


def detect_all(
    df: pd.DataFrame,
    sic_code: str | None = None,
) -> pd.DataFrame:
    """Combine Z-score and rule-based anomalies into a single DataFrame."""
    zscore_df = detect_zscore_anomalies(df)
    rule_df   = detect_rule_based_anomalies(df, sic_code=sic_code)

    combined = pd.concat([zscore_df, rule_df], ignore_index=True)
    if combined.empty:
        return pd.DataFrame(columns=COLUMNS)

    return (
        combined
        .sort_values(["period", "severity"], ascending=[False, True])
        .reset_index(drop=True)
    )
