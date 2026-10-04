from datetime import date
import pytest

from member2.schemas import EvidencePolarity, EvidenceSource
from member2.temporal import extract_temporal_evidence

REF_DATE = date(2026, 10, 3)


def test_fire_happening_today():
    text = "There is a massive fire happening today near the metro station"
    evidence = extract_temporal_evidence(text, reference_date=REF_DATE)

    assert len(evidence) >= 1
    # Matches "happening today" (or "today")
    assert any(e.polarity == EvidencePolarity.CURRENT for e in evidence)
    assert any("happening today" in e.finding or "today" in e.finding for e in evidence)
    assert evidence[0].source == EvidenceSource.TEXT


def test_fire_happened_yesterday():
    text = "Fire happened yesterday near the market"
    evidence = extract_temporal_evidence(text, reference_date=REF_DATE)

    assert len(evidence) >= 1
    assert any("yesterday" in e.finding.lower() for e in evidence)
    assert evidence[0].details["offset_days"] == -1


def test_explosion_in_2021():
    text = "Explosion happened in 2021 at the chemical warehouse"
    evidence = extract_temporal_evidence(text, reference_date=REF_DATE)

    assert len(evidence) >= 1
    old_evidence = [e for e in evidence if e.polarity == EvidencePolarity.OLD]
    assert len(old_evidence) >= 1
    assert any(e.details.get("year") == 2021 for e in old_evidence)


def test_flood_on_june_12_2021():
    text = "Flood on June 12, 2021 destroyed several bridges"
    evidence = extract_temporal_evidence(text, reference_date=REF_DATE)

    assert len(evidence) >= 1
    assert evidence[0].polarity == EvidencePolarity.OLD
    assert evidence[0].details["date"] == "2021-06-12"
    assert evidence[0].weight >= 0.85


def test_old_video_from_2021():
    text = "This is an old video from 2021 being circulated again"
    evidence = extract_temporal_evidence(text, reference_date=REF_DATE)

    assert len(evidence) >= 1
    # Both "old video" and "from 2021" or matched historical flag
    assert all(e.polarity == EvidencePolarity.OLD for e in evidence)
    assert any("historical" in e.finding.lower() or "2021" in e.finding for e in evidence)


def test_incident_happening_now():
    text = "The incident is happening now, multiple teams are on site"
    evidence = extract_temporal_evidence(text, reference_date=REF_DATE)

    assert len(evidence) >= 1
    assert evidence[0].polarity == EvidencePolarity.CURRENT
    assert "happening now" in evidence[0].finding.lower()
    assert evidence[0].weight >= 0.85


def test_flood_last_year():
    text = "There was a flood last year in this area"
    evidence = extract_temporal_evidence(text, reference_date=REF_DATE)

    assert len(evidence) >= 1
    assert evidence[0].polarity == EvidencePolarity.OLD
    assert "last year" in evidence[0].finding.lower()


def test_recently_there_was_a_fire():
    text = "Recently there was a fire in the industrial sector"
    evidence = extract_temporal_evidence(text, reference_date=REF_DATE)

    assert len(evidence) >= 1
    assert evidence[0].polarity == EvidencePolarity.NEUTRAL
    assert evidence[0].details.get("uncertainty") is True
    assert evidence[0].weight <= 0.50


def test_text_with_no_temporal_information():
    text = "A severe traffic jam on the main highway due to vehicle breakdown"
    evidence = extract_temporal_evidence(text, reference_date=REF_DATE)

    assert evidence == []


def test_multiple_temporal_expressions():
    text = "Breaking: Old video from 2021 is being falsely shared as happening today"
    evidence = extract_temporal_evidence(text, reference_date=REF_DATE)

    assert len(evidence) >= 2
    polarities = [e.polarity for e in evidence]
    assert EvidencePolarity.CURRENT in polarities  # "Breaking" / "happening today"
    assert EvidencePolarity.OLD in polarities      # "Old video" / "from 2021"


def test_invalid_and_empty_text():
    assert extract_temporal_evidence(None, reference_date=REF_DATE) == []
    assert extract_temporal_evidence("", reference_date=REF_DATE) == []
    assert extract_temporal_evidence("   \n\t  ", reference_date=REF_DATE) == []
    assert extract_temporal_evidence(12345, reference_date=REF_DATE) == []  # type: ignore


def test_iso_date_and_relative_boundary():
    # Date within 7 days of reference (CURRENT)
    near_text = "Incident report for 2026-10-02"
    near_ev = extract_temporal_evidence(near_text, reference_date=REF_DATE)
    assert len(near_ev) == 1
    assert near_ev[0].polarity == EvidencePolarity.CURRENT

    # Date far in past (OLD)
    old_text = "Incident report for 2013-06-12"
    old_ev = extract_temporal_evidence(old_text, reference_date=REF_DATE)
    assert len(old_ev) == 1
    assert old_ev[0].polarity == EvidencePolarity.OLD


def test_vague_relative_phrases_detected_as_old():
    phrases = [
        "This earthquake happened several years ago.",
        "This earthquake happened a few years ago.",
        "This earthquake happened many years ago.",
        "This earthquake happened a couple of years ago.",
        "The wildfire occurred couple of years ago.",
        "The bridge collapsed few years ago.",
    ]
    for text in phrases:
        ev = extract_temporal_evidence(text, reference_date=REF_DATE)
        assert len(ev) >= 1, f"Failed to extract evidence for: {text!r}"
        assert any(e.polarity == EvidencePolarity.OLD for e in ev), (
            f"Expected OLD polarity for: {text!r}, got {[e.polarity for e in ev]}"
        )
        assert any("relative_ago" in e.details.get("type", "") for e in ev)

