"""
test_conflict_and_ocr_regression.py
Comprehensive regression tests for:
1. Cross-modal category conflict detection (Cyclone text vs Earthquake video/image).
2. Matching text and visual category (no false conflict).
3. Video OCR fixture with visible text/date extraction and provenance.
4. Distinguishing OCR engine unavailable / execution failure from empty text extraction.
5. End-to-end persistence and API reconstruction of has_conflict and conflicts_detected.
6. Temporal uncertainty without category contradiction (UNCERTAIN verdict without false conflict).

All tests use isolated in-memory SQLite databases and NEVER modify crisissense.db.
"""

from __future__ import annotations

import io
import os
import tempfile
from datetime import date
from typing import Generator
from unittest.mock import patch

import cv2
import numpy as np
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from member2.schemas import (
    CurrentnessVerdict,
    EvidenceItem,
    EvidencePolarity,
    EvidenceSource,
    Member1Context,
    VerificationAction,
)
from member2.fusion import (
    fuse_evidence,
    detect_conflicts,
    detect_category_conflicts,
    CATEGORY_COMPATIBILITY,
    CATEGORY_CONFLICT_THRESHOLD,
)
from member2.ocr import (
    extract_ocr_evidence,
    extract_ocr_text,
    run_ocr_with_status,
    is_tesseract_available,
)
from member2.video import extract_video_evidence, sample_video_frames
from member3.database import Base, get_db
from member3.models import Incident, Report
from main import app, _get_report_conflicts, _format_currentness

REF_DATE = date(2026, 10, 14)


# ---------------------------------------------------------------------------
# Test Fixtures & In-Memory DB Setup
# ---------------------------------------------------------------------------

@pytest.fixture
def isolated_db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def isolated_client(isolated_db: Session) -> Generator[TestClient, None, None]:
    def _override_get_db():
        yield isolated_db

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_db, None)


def _create_video_fixture_with_text(text: str, duration_sec: float = 1.5, fps: int = 10) -> str:
    """Creates a temporary MP4/AVI video file with visible text drawn in the frames."""
    fd, path = tempfile.mkstemp(suffix=".avi")
    os.close(fd)

    width, height = 640, 360
    total_frames = int(duration_sec * fps)
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    out = cv2.VideoWriter(path, fourcc, float(fps), (width, height))

    for _ in range(total_frames):
        frame = np.ones((height, width, 3), dtype=np.uint8) * 255
        cv2.putText(
            frame,
            text,
            (40, height // 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (0, 0, 0),
            2,
            cv2.LINE_AA,
        )
        out.write(frame)

    out.release()
    return path


# ---------------------------------------------------------------------------
# Test 1: Cross-Modal Conflict Detection (Cyclone Text vs Earthquake Visual)
# ---------------------------------------------------------------------------

def test_cross_modal_conflict_cyclone_text_vs_earthquake_visual():
    """Text indicates Cyclone, while high-confidence visual evidence indicates Earthquake."""
    m1_context = Member1Context(
        is_crisis=True,
        incident_type="Cyclone",
        severity="CRITICAL",
    )

    evidence = [
        EvidenceItem(
            source=EvidenceSource.TEXT,
            finding="Citizen reports cyclone in Coimbatore",
            polarity=EvidencePolarity.NEUTRAL,
            weight=0.88,
        ),
        EvidenceItem(
            source=EvidenceSource.IMAGE_CLASSIFICATION,
            finding="Video frame 0 (t=0.0s): Visual analysis suggests Earthquake (confidence 0.99)",
            polarity=EvidencePolarity.NEUTRAL,
            weight=0.99,
            details={
                "predicted_class": "earthquake",
                "confidence": 0.9947,
                "frame_index": 0,
                "timestamp_seconds": 0.0,
            },
        ),
        EvidenceItem(
            source=EvidenceSource.IMAGE_CLASSIFICATION,
            finding="Video frame 168 (t=5.6s): Visual analysis suggests Earthquake (confidence 0.85)",
            polarity=EvidencePolarity.NEUTRAL,
            weight=0.85,
            details={
                "predicted_class": "earthquake",
                "confidence": 0.8512,
                "frame_index": 168,
                "timestamp_seconds": 5.6,
            },
        ),
    ]

    result = fuse_evidence(evidence=evidence, member1_context=m1_context)

    assert result.has_conflict is True
    assert len(result.conflicts_detected) >= 1
    conflict_desc = result.conflicts_detected[0]
    assert "Cyclone" in conflict_desc
    assert "Earthquake" in conflict_desc
    assert "incompatible" in conflict_desc.lower() or "contradict" in conflict_desc.lower()
    assert result.currentness == CurrentnessVerdict.UNCERTAIN
    assert result.action == VerificationAction.HUMAN_VERIFICATION_REQUIRED


# ---------------------------------------------------------------------------
# Test 2: Matching Text and Visual Category (No Conflict)
# ---------------------------------------------------------------------------

def test_matching_text_and_visual_category_no_conflict():
    """Text indicates Earthquake, and visual evidence indicates Earthquake -> No conflict."""
    m1_context = Member1Context(
        is_crisis=True,
        incident_type="Earthquake",
        severity="HIGH",
    )

    evidence = [
        EvidenceItem(
            source=EvidenceSource.TEXT,
            finding="Ground shaking violently in Delhi",
            polarity=EvidencePolarity.NEUTRAL,
            weight=0.90,
        ),
        EvidenceItem(
            source=EvidenceSource.IMAGE_CLASSIFICATION,
            finding="Visual analysis suggests Earthquake (confidence 0.94)",
            polarity=EvidencePolarity.NEUTRAL,
            weight=0.94,
            details={
                "predicted_class": "earthquake",
                "confidence": 0.94,
            },
        ),
    ]

    result = fuse_evidence(evidence=evidence, member1_context=m1_context)

    assert result.has_conflict is False
    assert result.conflicts_detected == []
    assert result.currentness == CurrentnessVerdict.UNCERTAIN  # No temporal claims yet


# ---------------------------------------------------------------------------
# Test 3: Video OCR Fixture with Known Visible Text/Date
# ---------------------------------------------------------------------------

def test_video_ocr_extracts_known_visible_date():
    """Generates a video with visible text 'INCIDENT: EARTHQUAKE 2018-09-12' and asserts extraction."""
    if not is_tesseract_available():
        pytest.skip("Tesseract OCR binary is not installed on this system")

    vid_path = _create_video_fixture_with_text("INCIDENT: EARTHQUAKE 2018-09-12", duration_sec=1.0, fps=10)
    try:
        evidence = extract_video_evidence(video_path=vid_path, reference_date=REF_DATE, max_frames=3)
        assert len(evidence) >= 2  # metadata + at least one OCR item

        ocr_items = [e for e in evidence if e.source == EvidenceSource.OCR]
        assert len(ocr_items) >= 1

        # Assert that the historical date 2018-09-12 was detected and flagged as OLD
        historical_items = [e for e in ocr_items if e.polarity == EvidencePolarity.OLD]
        assert len(historical_items) >= 1
        assert "2018-09-12" in str(historical_items[0].details.get("date"))
        assert "frame_index" in historical_items[0].details
        assert "timestamp_seconds" in historical_items[0].details
    finally:
        if os.path.exists(vid_path):
            os.remove(vid_path)


# ---------------------------------------------------------------------------
# Test 4: OCR Engine Unavailable / Failure vs Empty Extraction
# ---------------------------------------------------------------------------

def test_ocr_engine_unavailable_distinguished_from_empty():
    """Asserts that when Tesseract is unavailable, status is UNAVAILABLE, not EXECUTED_NO_TEXT."""
    with patch("member2.ocr.is_tesseract_available", return_value=False):
        dummy_img = Image.new("RGB", (100, 100), color=(255, 255, 255))
        res = run_ocr_with_status(dummy_img)
        assert res["status"] == "UNAVAILABLE"
        assert res["text"] == ""

        evidence = extract_ocr_evidence(dummy_img, reference_date=REF_DATE)
        assert len(evidence) == 1
        assert evidence[0].details["status"] == "UNAVAILABLE"
        assert "unavailable" in evidence[0].finding.lower()


def test_ocr_execution_failure_distinguished_from_empty():
    """Asserts that when OCR raises an unexpected exception, status is FAILED."""
    with patch("member2.ocr.is_tesseract_available", return_value=True):
        with patch("pytesseract.image_to_string", side_effect=RuntimeError("Tesseract segfault simulator")):
            dummy_img = Image.new("RGB", (100, 100), color=(255, 255, 255))
            res = run_ocr_with_status(dummy_img)
            assert res["status"] == "FAILED"
            assert "segfault" in res["error"]

            evidence = extract_ocr_evidence(dummy_img, reference_date=REF_DATE)
            assert len(evidence) == 1
            assert evidence[0].details["status"] == "FAILED"
            assert "failed" in evidence[0].finding.lower()


def test_ocr_clean_execution_with_no_text():
    """Asserts that a blank image produces EXECUTED_NO_TEXT with appropriate finding."""
    if not is_tesseract_available():
        pytest.skip("Tesseract OCR binary is not installed on this system")

    blank_img = Image.new("RGB", (200, 200), color=(255, 255, 255))
    res = run_ocr_with_status(blank_img)
    assert res["status"] == "EXECUTED_NO_TEXT"
    assert res["text"] == ""

    evidence = extract_ocr_evidence(blank_img, reference_date=REF_DATE)
    assert len(evidence) == 1
    assert evidence[0].details["status"] == "EXECUTED_NO_TEXT"
    assert "no readable text" in evidence[0].finding.lower()


# ---------------------------------------------------------------------------
# Test 5: End-to-End Conflict Persistence and API Reconstruction
# ---------------------------------------------------------------------------

def test_conflict_survives_analysis_and_incident_retrieval(isolated_client: TestClient, isolated_db: Session):
    """
    Submits a report with cyclone text and earthquake visual evidence.
    Verifies that has_conflict: True and conflicts_detected survive in GET /incidents and GET /incidents/{id}.
    """
    # Create incident and report with cyclone text and earthquake visual evidence
    incident = Incident(
        id="INC-TEST-CONFLICT-001",
        incident_type="Cyclone",
        location_name="Coimbatore",
        latitude=11.0168,
        longitude=76.9558,
        severity="CRITICAL",
        needs=["rescue", "medical"],
        verification_status="PENDING",
        status="OPEN",
    )
    isolated_db.add(incident)
    isolated_db.flush()

    report = Report(
        id="REP-TEST-CONFLICT-001",
        incident_id=incident.id,
        original_text="Cyclone occured at Coimbatore, people in trouble",
        crisis_analysis={
            "is_crisis": True,
            "incident_type": "Cyclone",
            "severity": "CRITICAL",
            "crisis_probability": 0.95,
        },
        currentness_assessment={
            "currentness": "UNCERTAIN",
            "confidence": 0.20,
            "action": "HUMAN_VERIFICATION_REQUIRED",
            "has_conflict": True,
            "conflicts_detected": [
                "Cross-modal category conflict: Citizen text indicates 'Cyclone' while visual evidence indicates 'Earthquake'."
            ],
            "evidence": [
                {
                    "source": "image_classification",
                    "polarity": "NEUTRAL",
                    "weight": 0.95,
                    "finding": "Visual analysis suggests Earthquake (confidence 0.95)",
                    "details": {"predicted_class": "earthquake", "confidence": 0.95},
                }
            ],
        },
    )
    isolated_db.add(report)
    isolated_db.commit()

    # 1. Test GET /incidents
    resp = isolated_client.get("/incidents")
    assert resp.status_code == 200
    incidents = resp.json()
    matched = next((inc for inc in incidents if inc["incident_id"] == "INC-TEST-CONFLICT-001"), None)
    assert matched is not None
    assert matched["has_conflict"] is True

    # 2. Test GET /incidents/{id}
    detail_resp = isolated_client.get(f"/incidents/{incident.id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["has_conflict"] is True
    assert len(detail["conflicts_detected"]) >= 1
    assert "Cyclone" in detail["conflicts_detected"][0]
    assert "Earthquake" in detail["conflicts_detected"][0]
    assert detail["reports"][0]["currentness"]["has_conflict"] is True


def test_conflict_reconstructed_for_historical_record(isolated_client: TestClient, isolated_db: Session):
    """
    Simulates the exact scenario of REP-d420ea6d12764c10ba7ea49061bab3ce:
    conflicts_detected was saved as [] initially, but crisis_analysis is Cyclone and
    evidence has visual prediction Earthquake.
    Verifies that the API dynamically reconstructs has_conflict: True and the conflict text.
    """
    incident = Incident(
        id="INC-HISTORICAL-001",
        incident_type="Cyclone",
        location_name="Coimbatore",
        latitude=11.0,
        longitude=76.9,
        severity="CRITICAL",
        needs=["rescue"],
        verification_status="PENDING",
        status="OPEN",
    )
    isolated_db.add(incident)
    isolated_db.flush()

    # Old report where conflicts_detected was saved as empty list []
    report = Report(
        id="REP-HISTORICAL-001",
        incident_id=incident.id,
        original_text="Cyclone occured at Coimbatore",
        crisis_analysis={
            "is_crisis": True,
            "incident_type": "Cyclone",
            "severity": "CRITICAL",
        },
        currentness_assessment={
            "currentness": "UNCERTAIN",
            "confidence": 0.0,
            "action": "HUMAN_VERIFICATION_REQUIRED",
            "conflicts_detected": [],  # Empty in legacy record
            "evidence": [
                {
                    "source": "video",
                    "polarity": "NEUTRAL",
                    "weight": 0.99,
                    "finding": "Video frame 0 (t=0.0s): Visual analysis suggests Earthquake (confidence 0.99)",
                    "details": {
                        "predicted_class": "earthquake",
                        "confidence": 0.9947,
                        "frame_index": 0,
                    },
                }
            ],
        },
    )
    isolated_db.add(report)
    isolated_db.commit()

    # Helper function check
    reconstructed = _get_report_conflicts(report)
    assert len(reconstructed) >= 1
    assert "Cyclone" in reconstructed[0]
    assert "Earthquake" in reconstructed[0]

    # Endpoint checks
    list_resp = isolated_client.get("/incidents")
    assert list_resp.status_code == 200
    inc_item = next((i for i in list_resp.json() if i["incident_id"] == "INC-HISTORICAL-001"), None)
    assert inc_item is not None
    assert inc_item["has_conflict"] is True

    detail_resp = isolated_client.get("/incidents/INC-HISTORICAL-001")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["has_conflict"] is True
    assert len(detail["conflicts_detected"]) >= 1


# ---------------------------------------------------------------------------
# Test 6: Temporal Uncertainty Without Modality Contradiction
# ---------------------------------------------------------------------------

def test_temporal_uncertainty_without_false_conflict():
    """
    When evidence has no temporal markers and no modality contradictions (e.g. Flood text + Flood visual),
    verdict is UNCERTAIN and action is HUMAN_VERIFICATION_REQUIRED, but has_conflict is FALSE.
    """
    m1_context = Member1Context(
        is_crisis=True,
        incident_type="Flood",
        severity="HIGH",
    )

    evidence = [
        EvidenceItem(
            source=EvidenceSource.TEXT,
            finding="Water level rising rapidly on Main Street",
            polarity=EvidencePolarity.NEUTRAL,
            weight=0.85,
        ),
        EvidenceItem(
            source=EvidenceSource.IMAGE_CLASSIFICATION,
            finding="Visual analysis suggests Flood (confidence 0.92)",
            polarity=EvidencePolarity.NEUTRAL,
            weight=0.92,
            details={
                "predicted_class": "flood",
                "confidence": 0.92,
            },
        ),
    ]

    result = fuse_evidence(evidence=evidence, member1_context=m1_context)

    assert result.currentness == CurrentnessVerdict.UNCERTAIN
    assert result.action == VerificationAction.HUMAN_VERIFICATION_REQUIRED
    assert result.has_conflict is False
    assert result.conflicts_detected == []
