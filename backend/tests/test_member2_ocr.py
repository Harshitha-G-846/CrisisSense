import io
import os
from datetime import date
from PIL import Image, PngImagePlugin
import pytest

from member2.schemas import EvidenceItem, EvidencePolarity, EvidenceSource
from member2.ocr import (
    load_image,
    extract_image_metadata,
    extract_ocr_text,
    extract_ocr_evidence,
    extract_image_evidence,
    is_tesseract_available
)

REF_DATE = date(2026, 10, 3)


def test_load_valid_and_invalid_image(tmp_path):
    # Valid image
    img = Image.new("RGB", (100, 100), color=(255, 255, 255))
    img_path = str(tmp_path / "test.png")
    img.save(img_path)

    loaded = load_image(img_path)
    assert loaded is not None
    assert loaded.size == (100, 100)

    # Invalid image path
    assert load_image(str(tmp_path / "non_existent.png")) is None
    assert load_image(None) is None
    assert load_image(12345) is None


def test_ocr_temporal_evidence_old():
    # Direct OCR evidence with simulated OCR text containing historical date
    evidence = extract_ocr_evidence(
        image_input="dummy_path.png",
        reference_date=REF_DATE,
        ocr_text_override="Flood on June 12, 2021 destroyed several buildings"
    )

    assert len(evidence) >= 1
    assert evidence[0].source == EvidenceSource.OCR
    assert evidence[0].polarity == EvidencePolarity.OLD
    assert "2021-06-12" in str(evidence[0].details.get("date"))


def test_ocr_temporal_evidence_current():
    evidence = extract_ocr_evidence(
        image_input="dummy_path.png",
        reference_date=REF_DATE,
        ocr_text_override="Fire happening today near the metro station"
    )

    assert len(evidence) >= 1
    assert evidence[0].source == EvidenceSource.OCR
    assert evidence[0].polarity == EvidencePolarity.CURRENT
    assert any("today" in e.finding.lower() for e in evidence)


def test_ocr_text_without_dates_is_neutral():
    evidence = extract_ocr_evidence(
        image_input="dummy_path.png",
        reference_date=REF_DATE,
        ocr_text_override="EMERGENCY EXIT ONLY NO PARKING"
    )

    assert len(evidence) == 1
    assert evidence[0].source == EvidenceSource.OCR
    assert evidence[0].polarity == EvidencePolarity.NEUTRAL


def test_ocr_empty_or_unavailable_is_neutral():
    evidence = extract_ocr_evidence(
        image_input="dummy_path.png",
        reference_date=REF_DATE,
        ocr_text_override=""
    )

    assert len(evidence) == 1
    assert evidence[0].source == EvidenceSource.OCR
    assert evidence[0].polarity == EvidencePolarity.NEUTRAL


def test_exif_metadata_extraction_when_present(tmp_path):
    img = Image.new("RGB", (50, 50), color=(200, 200, 200))
    exif = img.getexif()
    # 306 is DateTime tag in EXIF
    exif[306] = "2021:05:15 10:30:00"
    
    img_path = str(tmp_path / "exif_test.jpg")
    img.save(img_path, exif=exif)

    metadata_evidence = extract_image_metadata(img_path, reference_date=REF_DATE)
    assert len(metadata_evidence) == 1
    assert metadata_evidence[0].source == EvidenceSource.METADATA
    assert metadata_evidence[0].polarity == EvidencePolarity.OLD
    assert metadata_evidence[0].details["date"] == "2021-05-15"


def test_exif_metadata_missing_is_neutral(tmp_path):
    img = Image.new("RGB", (50, 50), color=(100, 100, 100))
    img_path = str(tmp_path / "no_exif.png")
    img.save(img_path)

    metadata_evidence = extract_image_metadata(img_path, reference_date=REF_DATE)
    assert len(metadata_evidence) == 1
    assert metadata_evidence[0].source == EvidenceSource.METADATA
    assert metadata_evidence[0].polarity == EvidencePolarity.NEUTRAL


def test_combined_extract_image_evidence(tmp_path):
    img = Image.new("RGB", (80, 80), color=(255, 255, 255))
    img_path = str(tmp_path / "combined.jpg")
    img.save(img_path)

    evidence = extract_image_evidence(
        img_path,
        reference_date=REF_DATE,
        ocr_text_override="Fire happening today"
    )

    sources = [e.source for e in evidence]
    assert EvidenceSource.METADATA in sources
    assert EvidenceSource.OCR in sources
    
    ocr_items = [e for e in evidence if e.source == EvidenceSource.OCR]
    assert ocr_items[0].polarity == EvidencePolarity.CURRENT


def test_real_ocr_execution_does_not_crash():
    img = Image.new("RGB", (100, 50), color=(255, 255, 255))
    text = extract_ocr_text(img)
    # Even if tesseract is missing on host, extract_ocr_text returns string without raising
    assert isinstance(text, str)
