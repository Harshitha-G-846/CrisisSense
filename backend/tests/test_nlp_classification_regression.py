"""
test_nlp_classification_regression.py — Regression tests for incident classification,
waterlogging domain preprocessing, typo tolerance, and truthful fallback analysis states.
"""
import pytest
from member1.pipeline import analyze_crisis, predict_crisis, clean_text
from member1.location_extractor import extract_locations, fuzzy_match_location


def test_waterlogging_jaisalmar_stuck_people_regression():
    """
    Regression test for:
    "waterlogging at jaisalmar since yesterday,people are stuck"
    Must be identified as a crisis, classified into flood category,
    severity assessed as HIGH, and location resolved to Jaisalmer despite typo.
    """
    text = "waterlogging at jaisalmar since yesterday,people are stuck"
    result = analyze_crisis(text)

    # 1. Must be recognized as an active crisis
    assert result["is_crisis"] is True
    assert result["crisis_probability"] is not None
    assert result["crisis_probability"] >= 0.50

    # 2. Category must identify flood emergency
    assert result["incident_type"] in ("Urban Flood", "Flood", "Flash Flood")

    # 3. Trapped/stuck people in flood water must yield HIGH or CRITICAL severity
    assert result["severity"] in ("HIGH", "CRITICAL")

    # 4. Location must be extracted and resolved to Jaisalmer, Rajasthan
    locations = result.get("locations") or []
    assert len(locations) > 0
    primary_loc = locations[0]
    assert "jaisalmer" in (primary_loc.get("city") or "").lower() or "jaisalmer" in (primary_loc.get("display_name") or "").lower()
    assert primary_loc.get("state") == "Rajasthan"
    assert primary_loc.get("latitude") is not None
    assert primary_loc.get("longitude") is not None


def test_clean_text_domain_normalization():
    """Verify clean_text normalizes South Asian disaster terminology without altering core context."""
    text1 = clean_text("Heavy waterlogging across roads")
    assert "flood" in text1
    assert "waterlogging" in text1

    text2 = clean_text("water-logging in low lying areas")
    assert "flood" in text2

    text3 = clean_text("severe inundation in district")
    assert "flood" in text3


def test_fire_and_earthquake_categories_preserved():
    """Ensure existing categories (Fire, Earthquake, etc.) continue to classify accurately."""
    fire_text = "huge fire spreading rapidly in factory near Whitefeild, several workers trapped"
    res_fire = analyze_crisis(fire_text)
    assert res_fire["is_crisis"] is True
    assert "fire" in (res_fire["incident_type"] or "").lower()
    assert res_fire["severity"] in ("HIGH", "CRITICAL")
    assert any("whitefield" in (loc.get("display_name") or "").lower() for loc in res_fire["locations"])

    eq_text = "major earthquake tremors felt in Hydrabad, buildings cracked"
    res_eq = analyze_crisis(eq_text)
    assert res_eq["is_crisis"] is True
    assert any("hyderabad" in (loc.get("display_name") or "").lower() for loc in res_eq["locations"])


def test_truthful_non_crisis_fallback():
    """Verify non-crisis / everyday messages return clear is_crisis=False and None category/severity."""
    non_crisis = "Going to the grocery store to buy apples and bread for dinner."
    res = analyze_crisis(non_crisis)
    assert res["is_crisis"] is False
    assert res["incident_type"] is None
    assert res["severity"] is None

    empty_res = analyze_crisis("")
    assert empty_res["is_crisis"] is False
    assert empty_res["incident_type"] is None
    assert empty_res["severity"] is None
    assert "No text provided" in empty_res["message"]
