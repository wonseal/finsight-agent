"""
Basic fact extractor for SEC companyfacts.

1. Create a FactExtractor object
2. Extract only the us-gaap facts from companyfacts
3. Convert metric_name into candidate XBRL tags using CONCEPT_MAP
4. Search each candidate tag one by one
5. Retrieve only the data with the USD unit
6. Keep only 10-K and 10-Q data
7. Store records that have value, fy, and fp in records
8. Convert records into a pandas DataFrame
9. For duplicate records with the same metric / fy / fp / form, keep only the latest one based on filed date
10. Return the cleaned data in a table-like format
"""


from __future__ import annotations

import pandas as pd

from src.xbrl.concept_map import CONCEPT_MAP


class FactExtractor:
    """Extract normalized financial facts from SEC companyfacts JSON."""

    def __init__(self, taxonomy: str = "us-gaap") -> None:
        self.taxonomy = taxonomy

    def extract_metric(
        self,
        companyfacts: dict,
        metric_name: str,
        unit: str = "USD",
        forms: tuple[str, ...] = ("10-K", "10-Q"),
    ) -> pd.DataFrame:
        """Extract one normalized metric from companyfacts.

        Example:
            metric_name="revenue"

        This searches all XBRL candidate tags listed in CONCEPT_MAP["revenue"].
        """
        if metric_name not in CONCEPT_MAP:
            raise ValueError(f"Unknown metric name: {metric_name}")
            # if the metric name is not in the CONCEPT_MAP, we cannot extract it from companyfacts, so we raise an error.

        facts = companyfacts.get("facts", {}).get(self.taxonomy, {})
        # using hash map to get specific taxonomy facts from companyfacts faster, e.g. "us-gaap" facts
        candidate_tags = CONCEPT_MAP[metric_name]

        records: list[dict] = []

        for tag in candidate_tags:
            # if the candidate tag is not in the facts, skip to the next tag. This is a common case since not all companies will use all possible tags for a given metric.  
            if tag not in facts:
                continue

            tag_data = facts[tag]
            unit_records = tag_data.get("units", {}).get(unit, [])

            for item in unit_records:
                if item.get("form") not in forms: # Only include facts from specified forms, e.g. 10-K and 10-Q.    
                    continue

                value = item.get("val")
                fy = item.get("fy")
                fp = item.get("fp")

                if value is None or fy is None or fp is None:
                    continue

                records.append(
                    {
                        "metric": metric_name,
                        "xbrl_tag": tag,
                        "value": value,
                        "unit": unit,
                        "fy": fy,
                        "fp": fp,
                        "form": item.get("form"),
                        "filed": item.get("filed"),
                        "start": item.get("start"),
                        "end": item.get("end"),
                        "frame": item.get("frame"),
                        "accn": item.get("accn"),
                    }
                )

        if not records:
            return pd.DataFrame(
                columns=[
                    "metric",
                    "xbrl_tag",
                    "value",
                    "unit",
                    "fy",
                    "fp",
                    "form",
                    "filed",
                    "start",
                    "end",
                    "frame",
                    "accn",
                ]
            )

        df = pd.DataFrame(records)
        return self._deduplicate_facts(df)

    def extract_all_metrics(
        self,
        companyfacts: dict,
        unit: str = "USD",
        forms: tuple[str, ...] = ("10-K", "10-Q"),
    ) -> pd.DataFrame:
        """Extract all metrics defined in CONCEPT_MAP."""
        frames: list[pd.DataFrame] = []

        for metric_name in CONCEPT_MAP:
            metric_df = self.extract_metric(
                companyfacts=companyfacts,
                metric_name=metric_name,
                unit=unit,
                forms=forms,
            )

            if not metric_df.empty:
                frames.append(metric_df)

        if not frames:
            return pd.DataFrame()

        return pd.concat(frames, ignore_index=True)

    def _deduplicate_facts(self, df: pd.DataFrame) -> pd.DataFrame:
        """Keep the latest filed record for each metric / fiscal period.

        SEC companyfacts can contain amended or repeated facts.
        For the MVP, we keep the latest filing for each metric, fy, fp, and form.
        """
        clean_df = df.copy()
        

        clean_df["filed"] = pd.to_datetime(clean_df["filed"], errors="coerce")

        clean_df = clean_df.sort_values( # Sort by filing date, ascending. The latest (most recent) filing will be last.
            ["metric", "fy", "fp", "form", "filed"],
            ascending=True,
        )

        clean_df = clean_df.drop_duplicates( # For each metric + fiscal period + form, keep only the latest filed record.
            subset=["metric", "fy", "fp", "form"],
            keep="last",
        )

        return clean_df.reset_index(drop=True) # Reset index after deduplication.