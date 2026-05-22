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
    "liabilities_to_assets",
    "ocf_to_net_income",
    "fcf_to_revenue",
]

COLUMNS = ["period", "metric", "value", "severity", "anomaly_type", "method", "message", "z_score"]

_RULE_MESSAGES = {
    "revenue_drop":                  "Revenue declined more than 20% YoY.",
    "revenue_spike":                 "Revenue grew more than 50% YoY.",
    "high_leverage":                 "Liabilities exceed 80% of total assets.",
    "earnings_cashflow_divergence":  "Net income is positive but operating cash flow is negative.",
    "ocf_quality_issue":             "Operating cash flow is less than 50% of net income.",
    "negative_gross_margin":         "Gross margin is negative — selling below cost.",
    "net_loss":                      "Company reported a net loss.",
    "liquidity_risk":                "Current ratio below 1.0 — short-term liabilities exceed current assets.",
    "margin_collapse":               "Operating margin dropped more than 10 percentage points YoY.",
}


def detect_zscore_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """Detect z-score-based anomalies in annual (FY) data."""
    annual = df[df["fp"] == "FY"].sort_values("fy").copy()
    records: list[dict] = []

    for metric in ZSCORE_METRICS:
        if metric not in annual.columns:
            continue

        series = annual[["fy", metric]].dropna(subset=[metric])
        if len(series) < 4:
            continue

        mean = series[metric].mean()
        std = series[metric].std()
        if std == 0 or np.isnan(std):
            continue

        for _, row in series.iterrows():
            z = (row[metric] - mean) / std
            abs_z = abs(z)
            # For the MVP, we set a z-score threshold of 2.0 for flagging anomalies, with severity levels based on the z-score magnitude.
            if abs_z < 2.0:
                continue

            records.append({
                "period":       int(row["fy"]),
                "metric":       metric,
                "value":        round(row[metric], 4),
                "severity":     "high" if abs_z >= 3.0 else "medium",
                "anomaly_type": "positive_spike" if z > 0 else "negative_spike",
                "method":       "zscore",
                "message":      f"z={z:+.2f} — metric deviated significantly from historical mean (μ={mean:.2f}, σ={std:.2f}).",
                "z_score":      round(z, 2),
            })

    if not records:
        return pd.DataFrame(columns=COLUMNS)

    return (
        pd.DataFrame(records)[COLUMNS]
        .sort_values(["period", "z_score"], key=lambda s: s.abs() if s.name == "z_score" else s, ascending=[False, False])
        .reset_index(drop=True)
    )


def detect_rule_based_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """Detect anomalies using rule-based financial heuristics."""
    annual = df[df["fp"] == "FY"].sort_values("fy").copy()
    records: list[dict] = []

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

        if "revenue_YoY" in annual.columns and not pd.isna(row.get("revenue_YoY")):
            yoy = row["revenue_YoY"]
            if yoy < -20:
                _add(fy, "revenue_YoY", yoy, "high", "revenue_drop")
            elif yoy > 50:
                _add(fy, "revenue_YoY", yoy, "medium", "revenue_spike")

        if "liabilities_to_assets" in annual.columns and not pd.isna(row.get("liabilities_to_assets")):
            if row["liabilities_to_assets"] > 0.8:
                _add(fy, "liabilities_to_assets", row["liabilities_to_assets"], "high", "high_leverage")

        if all(c in annual.columns for c in ["net_income", "operating_cash_flow"]):
            ni, ocf = row.get("net_income"), row.get("operating_cash_flow")
            if not (pd.isna(ni) or pd.isna(ocf)):
                if ni > 0 and ocf < 0:
                    _add(fy, "operating_cash_flow", ocf, "high", "earnings_cashflow_divergence")

        if "ocf_to_net_income" in annual.columns and not pd.isna(row.get("ocf_to_net_income")):
            if 0 < row["ocf_to_net_income"] < 0.5:
                _add(fy, "ocf_to_net_income", row["ocf_to_net_income"], "medium", "ocf_quality_issue")

        if "gross_margin" in annual.columns and not pd.isna(row.get("gross_margin")):
            if row["gross_margin"] < 0:
                _add(fy, "gross_margin", row["gross_margin"], "high", "negative_gross_margin")

        if "net_income" in annual.columns and not pd.isna(row.get("net_income")):
            if row["net_income"] < 0:
                _add(fy, "net_income", row["net_income"], "medium", "net_loss")

        if "current_ratio" in annual.columns and not pd.isna(row.get("current_ratio")):
            if row["current_ratio"] < 1.0:
                _add(fy, "current_ratio", row["current_ratio"], "high", "liquidity_risk")

    if "operating_margin" in annual.columns:
        margin_diff = annual["operating_margin"].diff()
        for idx, diff_val in margin_diff.items():
            if pd.isna(diff_val):
                continue
            if diff_val < -10:
                _add(annual.loc[idx, "fy"], "operating_margin", annual.loc[idx, "operating_margin"], "high", "margin_collapse")

    if not records:
        return pd.DataFrame(columns=COLUMNS)

    return (
        pd.DataFrame(records)[COLUMNS]
        .sort_values(["period", "severity"], ascending=[False, True])
        .reset_index(drop=True)
    )


def detect_all(df: pd.DataFrame) -> pd.DataFrame:
    """Combine z-score and rule-based anomalies into a single DataFrame."""
    zscore_df = detect_zscore_anomalies(df)
    rule_df = detect_rule_based_anomalies(df)

    combined = pd.concat([zscore_df, rule_df], ignore_index=True)
    if combined.empty:
        return pd.DataFrame(columns=COLUMNS)

    return (
        combined
        .sort_values(["period", "severity"], ascending=[False, True])
        .reset_index(drop=True)
    )
