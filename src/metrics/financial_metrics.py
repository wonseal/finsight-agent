

from __future__ import annotations

import numpy as np
import pandas as pd

from src.xbrl.concept_map import CONCEPT_MAP
from src.xbrl.fact_extractor import FactExtractor

class metric_builder:

    def build_metric_table(
        self,
        companyfacts: dict,
        metric_names: list[str],
        unit: str = "USD",
        forms: tuple[str, ...] = ("10-K", "10-Q"),
    ) -> pd.DataFrame:
        """Build a table of multiple metrics from companyfacts."""
        extractor = FactExtractor()

        all_records: list[dict] = []

        for metric_name in metric_names:
            metric_df = extractor.extract_metric(
                companyfacts=companyfacts,
                metric_name=metric_name,
                unit=unit,
                forms=forms,
            )
            all_records.append(metric_df)

        if not all_records:
            return pd.DataFrame()  # Return empty DataFrame if no records.

        combined_df = pd.concat(all_records, ignore_index=True)

        # Clean and normalize the combined DataFrame.
        clean_df = combined_df.dropna(subset=["value", "fy", "fp", "form"])

        # Convert 'value' to numeric, coercing errors to NaN.
        clean_df["value"] = pd.to_numeric(clean_df["value"], errors="coerce")

        # Pivot: metric → columns, (fy, fp, form) → rows.
        pivot_df = clean_df.pivot_table(
            index=["fy", "fp", "form"],
            columns="metric",
            values="value",
            aggfunc="last",
        ).reset_index()
        pivot_df.columns.name = None

        return pivot_df
    
    def add_growth_metrics(
            self, df: pd.DataFrame, metric_names: list[str]) -> pd.DataFrame:
        """Add YoY growth columns for specified metrics."""

        df = df.copy()
        annual_sorted = df[df["fp"] == "FY"].sort_values("fy")

        for m in metric_names:
            if m not in df.columns:
                continue
            growth = annual_sorted[m].pct_change() * 100
            df.loc[growth.index, f"{m}_YoY"] = growth

        return df
    
    def add_profitability_metrics(
            self, df: pd.DataFrame) -> pd.DataFrame:
        """Add profitability metrics like gross margin, operating margin, net margin."""

        df = df.copy()

        if "revenue" in df.columns and "gross_profit" in df.columns:
            df["gross_margin"] = (df["gross_profit"] / df["revenue"] * 100).replace([np.inf, -np.inf], np.nan)

        if "revenue" in df.columns and "operating_income" in df.columns:
            df["operating_margin"] = (df["operating_income"] / df["revenue"] * 100).replace([np.inf, -np.inf], np.nan)

        if "revenue" in df.columns and "net_income" in df.columns:
            df["net_margin"] = (df["net_income"] / df["revenue"] * 100).replace([np.inf, -np.inf], np.nan)

        if "assets" in df.columns and "net_income" in df.columns:
            df["ROA"] = (df["net_income"] / df["assets"] * 100).replace([np.inf, -np.inf], np.nan)

        if "equity" in df.columns and "net_income" in df.columns:
            df["ROE"] = (df["net_income"] / df["equity"] * 100).replace([np.inf, -np.inf], np.nan)

        return df

    def add_risk_ratios(
            self, df: pd.DataFrame) -> pd.DataFrame:
        """Add risk ratios like debt-to-equity, current ratio, quick ratio."""
        df = df.copy()

        if "liabilities" in df.columns and "equity" in df.columns:
            df["liabilities_to_equity"] = (df["liabilities"] / df["equity"]).replace([np.inf, -np.inf], np.nan)

        if "liabilities" in df.columns and "assets" in df.columns:
            df["liabilities_to_assets"] = (df["liabilities"] / df["assets"]).replace([np.inf, -np.inf], np.nan)

        if "total_debt" in df.columns and "equity" in df.columns:
            df["debt_to_equity"] = (df["total_debt"] / df["equity"]).replace([np.inf, -np.inf], np.nan)

        if "current_assets" in df.columns and "current_liabilities" in df.columns:
            df["current_ratio"] = (df["current_assets"] / df["current_liabilities"]).replace([np.inf, -np.inf], np.nan)

        if "current_assets" in df.columns and "inventory" in df.columns and "current_liabilities" in df.columns:
            df["quick_ratio"] = ((df["current_assets"] - df["inventory"]) / df["current_liabilities"]).replace([np.inf, -np.inf], np.nan)

        if "operating_cash_flow" in df.columns and "net_income" in df.columns:
            df["ocf_to_net_income"] = (df["operating_cash_flow"] / df["net_income"]).replace([np.inf, -np.inf], np.nan)

        if "operating_cash_flow" in df.columns and "capex" in df.columns:
            df["free_cash_flow"] = df["operating_cash_flow"] - df["capex"]
            if "net_income" in df.columns:
                df["fcf_to_net_income"] = (df["free_cash_flow"] / df["net_income"]).replace([np.inf, -np.inf], np.nan)
            if "revenue" in df.columns:
                df["fcf_to_revenue"] = (df["free_cash_flow"] / df["revenue"]).replace([np.inf, -np.inf], np.nan)

        return df
    
    def build_all(
            self,
            companyfacts: dict,
            metric_names: list[str],
            unit: str = "USD",
            forms: tuple[str, ...] = ("10-K", "10-Q"),
    ) -> pd.DataFrame:
        """Build a comprehensive metric table with all enhancements."""
        df = self.build_metric_table(companyfacts, metric_names, unit, forms)
        df = self.add_growth_metrics(df, metric_names)
        df = self.add_profitability_metrics(df)
        df = self.add_risk_ratios(df)
        return df