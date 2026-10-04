from datetime import date
import pytest

from member2.schemas import EvidenceItem, EvidencePolarity, EvidenceSource, Member1Context
from member2.reference import (
    load_reference_events,
    get_event_metadata,
    find_matching_events,
    extract_reference_evidence
)
from member2.temporal import extract_temporal_evidence


def test_reference_corpus_loads():
    events = load_reference_events()
    assert len(events) == 26
    # Check key fields exist on all entries
    for ev in events:
        assert "name" in ev
        assert "year" in ev
        assert "folder_name" in ev
        assert isinstance(ev["keywords"], list)


def test_get_known_event_metadata():
    ev = get_event_metadata("2012_Colorado_wildfires")
    assert ev is not None
    assert ev["name"] == "Colorado wildfires"
    assert ev["year"] == 2012
    assert ev["incident_type"] == "Wildfire"
    assert ev["start_date"] == "2012-06-08"


def test_historical_event_alignment_evidence():
    text = "Colorado wildfire destroyed several houses back in 2012"
    ref_date = date(2026, 10, 3)
    temporal_items = extract_temporal_evidence(text, reference_date=ref_date)
    ref_evidence = extract_reference_evidence(text, temporal_items=temporal_items)

    assert len(ref_evidence) >= 1
    assert ref_evidence[0].source == EvidenceSource.REFERENCE_CORPUS
    assert ref_evidence[0].polarity == EvidencePolarity.OLD
    assert ref_evidence[0].details["event_year"] == 2012
    assert "Colorado wildfires" in ref_evidence[0].finding


def test_unknown_input_does_not_produce_old_evidence():
    text = "Road construction underway near Koramangala 80ft road"
    temporal_items = extract_temporal_evidence(text)
    ref_evidence = extract_reference_evidence(text, temporal_items=temporal_items)

    # Unknown input has no matching event -> no false OLD evidence
    assert ref_evidence == []


def test_event_mention_without_temporal_alignment_is_neutral():
    text = "Remember the Colorado wildfires tragedy"
    # No temporal items passed
    ref_evidence = extract_reference_evidence(text, temporal_items=[])

    assert len(ref_evidence) == 1
    # Mentioning a past event name without confirming timestamp is contextual/neutral
    assert ref_evidence[0].polarity == EvidencePolarity.NEUTRAL
    assert ref_evidence[0].weight < 0.50


def test_missing_directory_handled_safely():
    events = load_reference_events(data_dir="/tmp/non_existent_crisislex_dir")
    assert events == []
    ev = get_event_metadata("2012_Colorado_wildfires", data_dir="/tmp/non_existent_crisislex_dir")
    assert ev is None
    ref_ev = extract_reference_evidence("Colorado wildfire 2012", data_dir="/tmp/non_existent_crisislex_dir")
    assert ref_ev == []
