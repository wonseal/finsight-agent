from __future__ import annotations

import pandas as pd

from src.schemas.event import EventAttribution

SEVERITY_SCORE = {
    "high":   25,
    "medium": 15,
    "low":     5,
}

ANOMALY_TYPE_SCORE = {
    "earnings_cashflow_divergence": 20,
    "revenue_drop":                 20,
    "margin_collapse":              15,
    "high_leverage":                15,
    "negative_gross_margin":        15,
    "liquidity_risk":               15,
    "net_loss":                     10,
    "ocf_quality_issue":            10,
    "revenue_spike":                 5,
    "margin_pressure":              10,
    "cashflow_issue":               10,
    "debt_increase":                10,
}

UNEXPLAINED_BONUS = 15


def _priority_label(score: float) -> str:
    if score >= 61:
        return "high_review_priority"
    if score >= 31:
        return "medium_review_priority"
    return "low_review_priority"


def _reason(anomaly: dict, event_attribution: EventAttribution | None) -> str:
    explained = event_attribution is not None and event_attribution.event_found
    severity = anomaly.get("severity", "")

    if explained:
        return "Anomaly is explained by filing disclosure."
    if severity == "high":
        return "High-severity anomaly without supporting disclosure."
    return "Anomaly detected but no matching filing disclosure found."


class RiskScorer:

    def score_anomaly(
        self,
        anomaly: dict,
        event_attribution: EventAttribution | None = None,
    ) -> dict:
        """Compute the review priority score for a single anomaly."""
        score = 0

        score += SEVERITY_SCORE.get(anomaly.get("severity", ""), 0)
        score += ANOMALY_TYPE_SCORE.get(anomaly.get("anomaly_type", ""), 0)

        if event_attribution is None or not event_attribution.event_found:
            score += UNEXPLAINED_BONUS

        return {
            "period":       anomaly.get("period"),
            "metric":       anomaly.get("metric"),
            "anomaly_type": anomaly.get("anomaly_type"),
            "severity":     anomaly.get("severity"),
            "score":        score,
            "status":       _priority_label(score),
            "reason":       _reason(anomaly, event_attribution),
            "event_found":  event_attribution.event_found if event_attribution else False,
            "event_type":   event_attribution.event_type if event_attribution else "unexplained",
            "confidence":   event_attribution.confidence if event_attribution else 0.0,
        }

    def score_company(
        self,
        anomalies_df: pd.DataFrame,
        event_results: dict[str, EventAttribution] | None = None,
    ) -> pd.DataFrame:
        """Score all anomalies for a company and return as a DataFrame.

        Args:
            anomalies_df: DataFrame returned by detect_all().
            event_results: mapping of {anomaly key → EventAttribution}. If None, all anomalies are treated as unexplained.
        """
        if event_results is None:
            event_results = {}

        rows = []
        for _, row in anomalies_df.iterrows():
            anomaly = row.to_dict()
            key = f"{anomaly.get('period')}_{anomaly.get('metric')}"
            attribution = event_results.get(key)
            rows.append(self.score_anomaly(anomaly, attribution))

        if not rows:
            return pd.DataFrame()

        return (
            pd.DataFrame(rows)
            .sort_values("score", ascending=False)
            .reset_index(drop=True)
        )
