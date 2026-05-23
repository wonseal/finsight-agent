from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

EventType = Literal[
    "demand_growth",
    "acquisition",
    "divestiture",
    "new_product",
    "price_increase",
    "cost_reduction",
    "restructuring",
    "impairment",
    "macroeconomic_factor",
    "accounting_change",
    "margin_pressure",
    "cashflow_issue",
    "debt_increase",
    "unexplained",
    "other",
]


class EventAttribution(BaseModel):
    event_found: bool
    event_type: EventType
    explanation: str
    source_form: str
    source_filing_date: str
    confidence: float = Field(ge=0.0, le=1.0)
    @model_validator(mode="after")
    def check_unfound_event_type(self) -> EventAttribution:
        if not self.event_found:
            self.event_type = "unexplained"
        return self

    
