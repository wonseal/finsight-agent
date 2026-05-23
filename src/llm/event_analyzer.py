from __future__ import annotations

import json

import openai
import pandas as pd

from src.schemas.event import EventAttribution
from src.llm.prompts import SYSTEM_PROMPT, build_user_prompt
from src.sec.filing_downloader import FilingDownloader
from src.events.filling_parser import FilingParser


class EventAnalyzer:

    def __init__(self, openai_client: openai.OpenAI, downloader: FilingDownloader) -> None:
        self.client = openai_client
        self.downloader = downloader
        self.parser = FilingParser()

    def find_best_attribution(
        self,
        candidates: pd.DataFrame,
        cik: str,
        anomaly: dict,
        model: str = "gpt-4o-mini",
        top_n: int = 3,
    ) -> EventAttribution:
        """Return the best attribution from candidate filings.

        Analyzes only the top top_n filings in 10-K → 10-Q → 8-K priority order.
        Returns the result with the highest confidence among event_found=True results.
        Returns an unexplained attribution if none are found.
        """
        FORM_PRIORITY = {"10-K": 0, "10-Q": 1, "8-K": 2}

        sorted_candidates = (
            candidates
            .assign(_priority=candidates["form"].map(lambda f: FORM_PRIORITY.get(f, 99)))
            .sort_values("_priority")
            .drop(columns="_priority")
            .head(top_n)
            .reset_index(drop=True)
        )

        attributions = self.analyze_filings(sorted_candidates, cik, anomaly, model)

        found = [a for a in attributions if a.event_found]
        if found:
            return max(found, key=lambda a: a.confidence)

        return EventAttribution(
            event_found=False,
            event_type="unexplained",
            explanation="No candidate filing explained this anomaly.",
            source_form="",
            source_filing_date="",
            confidence=0.0,
        )

    def analyze_filings(
        self,
        candidates: pd.DataFrame,
        cik: str,
        anomaly: dict,
        model: str = "gpt-4o-mini",
    ) -> list[EventAttribution]:
        """Call the LLM for each candidate filing and return a list of EventAttributions."""
        results: list[EventAttribution] = []

        for _, row in candidates.iterrows():
            # download filing → plain text → relevant excerpt
            html = self.downloader.download_primary_document(
                cik, row["accessionNumber"], row["primaryDocument"]
            )
            text = self.parser.html_to_text(html)
            excerpt = self.parser.extract_relevant_sections(text)

            source_form = row["form"]
            source_filing_date = str(row["filingDate"].date())

            if not excerpt.strip():
                continue

            # call LLM; fall back to keyword rules on failure
            try:
                user_prompt = build_user_prompt(
                    period=anomaly["period"],
                    metric=anomaly["metric"],
                    value=anomaly["value"],
                    anomaly_type=anomaly["anomaly_type"],
                    severity=anomaly["severity"],
                    source_form=source_form,
                    source_filing_date=source_filing_date,
                    excerpt=excerpt,
                )
                response = self.client.chat.completions.create(
                    model=model,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                )
                raw = json.loads(response.choices[0].message.content)
                attribution = EventAttribution(**raw)
            except Exception:
                attribution = self._fallback_analyze(excerpt, source_form, source_filing_date)

            results.append(attribution)

        return results

    def _fallback_analyze(
        self, excerpt: str, source_form: str, source_filing_date: str
    ) -> EventAttribution:
        """Estimate event_type using keyword matching when the LLM call fails."""
        lower = excerpt.lower()

        KEYWORD_RULES = [
            ("acquisition",                          "acquisition"),
            ("customer demand",                      "demand_growth"),
            ("demand",                               "demand_growth"),
            ("restructuring",                        "restructuring"),
            ("impairment",                           "impairment"),
            ("macroeconomic",                        "macroeconomic_factor"),
            ("inflation",                            "macroeconomic_factor"),
            ("new product",                          "new_product"),
            ("price increase",                       "price_increase"),
            ("cost reduction",                       "cost_reduction"),
            ("margin pressure",                      "margin_pressure"),
            ("cash flow",                            "cashflow_issue"),
            ("debt",                                 "debt_increase"),
        ]

        for keyword, event_type in KEYWORD_RULES:
            if keyword in lower:
                return EventAttribution(
                    event_found=True,
                    event_type=event_type,
                    explanation=f"[fallback] Keyword '{keyword}' found in excerpt.",
                    source_form=source_form,
                    source_filing_date=source_filing_date,
                    confidence=0.4,
                )

        return EventAttribution(
            event_found=False,
            event_type="unexplained",
            explanation="[fallback] No matching keywords found in excerpt.",
            source_form=source_form,
            source_filing_date=source_filing_date,
            confidence=0.0,
        )
