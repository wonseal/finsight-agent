from src.schemas.event import EventAttribution


def test_event_type_preserved_when_found():
    e = EventAttribution(
        event_found=True,
        event_type="acquisition",
        explanation="",
        source_form="8-K",
        source_filing_date="2024-04-01",
        confidence=0.9,
    )
    assert e.event_type == "acquisition"


def test_event_type_set_to_unexplained_when_not_found():
    e = EventAttribution(
        event_found=False,
        event_type="acquisition",
        explanation="",
        source_form="",
        source_filing_date="",
        confidence=0.5,
    )
    assert e.event_type == "unexplained"
