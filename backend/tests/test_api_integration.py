"""
test_api_integration.py
Integration tests for the combined Member 1 + Member 2 FastAPI endpoints.
No network calls, no Whisper downloads, no external datasets.
"""

from __future__ import annotations

import io
import os
import tempfile
import numpy as np
import pytest
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient

from main import app
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from member3.database import Base, get_db

from sqlalchemy.pool import StaticPool

# Isolate tests into an in-memory SQLite database so crisissense.db is NEVER modified
_test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestingSessionLocal = sessionmaker(
    bind=_test_engine,
    autoflush=False,
    expire_on_commit=False,
)
Base.metadata.create_all(bind=_test_engine)

def _override_get_db():
    with _TestingSessionLocal() as session:
        yield session

@pytest.fixture(autouse=True)
def ensure_db_override():
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides[get_db] = _override_get_db

app.dependency_overrides[get_db] = _override_get_db

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _png_bytes(color=(200, 100, 50)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (80, 80), color=color).save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


def _avi_bytes() -> bytes:
    """Create a minimal valid AVI video in memory using OpenCV."""
    import tempfile
    import cv2
    with tempfile.NamedTemporaryFile(suffix=".avi", delete=False) as tf:
        path = tf.name
    try:
        fourcc = cv2.VideoWriter_fourcc(*"MJPG")
        out = cv2.VideoWriter(path, fourcc, 10.0, (64, 64))
        for _ in range(10):
            frame = np.zeros((64, 64, 3), dtype=np.uint8)
            out.write(frame)
        out.release()
        with open(path, "rb") as f:
            return f.read()
    finally:
        if os.path.exists(path):
            os.remove(path)


# ---------------------------------------------------------------------------
# 1. GET / health check
# ---------------------------------------------------------------------------

def test_home_endpoint():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "CrisisSense" in resp.json()["message"]


# ---------------------------------------------------------------------------
# 2. /analyze-text — text-only JSON (backwards compatibility)
# ---------------------------------------------------------------------------

def test_analyze_text_returns_combined_result():
    resp = client.post(
        "/analyze-text",
        json={"text": "Flood is happening today near the city."},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "crisis_analysis" in body
    assert "currentness" in body
    assert "is_crisis" in body["crisis_analysis"]
    # Active 'today' → CURRENT verdict expected
    assert body["currentness"]["currentness"] == "CURRENT"


def test_analyze_text_historical_produces_old():
    resp = client.post(
        "/analyze-text",
        json={"text": "The earthquake in 2015 destroyed many buildings."},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["currentness"]["currentness"] == "OLD"
    assert body["crisis_analysis"]["is_crisis"] is not None


def test_analyze_text_preserves_member1_fields():
    resp = client.post(
        "/analyze-text",
        json={"text": "Wildfire happening now in northern California."},
    )
    m1 = resp.json()["crisis_analysis"]
    assert "is_crisis" in m1
    assert "incident_type" in m1
    assert "information_type" in m1
    assert "severity" in m1
    assert "needs" in m1
    assert "locations" in m1


# ---------------------------------------------------------------------------
# 3. /analyze — multipart form-data: text only
# ---------------------------------------------------------------------------

def test_analyze_form_text_only():
    resp = client.post("/analyze", data={"text": "Heavy rains flooded the area today."})
    assert resp.status_code == 200
    body = resp.json()
    assert "crisis_analysis" in body
    assert "currentness" in body
    assert body["currentness"]["currentness"] == "CURRENT"


# ---------------------------------------------------------------------------
# 4. /analyze — text + image reaches Member 2
# ---------------------------------------------------------------------------

def test_analyze_text_plus_image():
    resp = client.post(
        "/analyze",
        data={"text": "Fire spotted near the bridge today!"},
        files={"image": ("fire_scene.png", _png_bytes(), "image/png")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "currentness" in body
    evidence_sources = [e["source"] for e in body["currentness"]["evidence"]]
    assert "text" in evidence_sources or "ocr" in evidence_sources or "metadata" in evidence_sources


# ---------------------------------------------------------------------------
# 5. /analyze — text + video reaches Member 2
# ---------------------------------------------------------------------------

def test_analyze_text_plus_video():
    video_data = _avi_bytes()
    resp = client.post(
        "/analyze",
        data={"text": "Footage of the cyclone damage."},
        files={"video": ("damage_clip.avi", video_data, "video/x-msvideo")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "currentness" in body
    evidence_sources = [e["source"] for e in body["currentness"]["evidence"]]
    assert "metadata" in evidence_sources


# ---------------------------------------------------------------------------
# 6. /analyze — text + audio (transcript override via empty audio won't load Whisper)
#    We test audio field acceptance; actual Whisper is only invoked live.
#    We pass a 0-byte WAV header (invalid content) to confirm graceful degradation.
# ---------------------------------------------------------------------------

def test_analyze_text_plus_audio_graceful_degradation():
    # Provide a minimal WAV-like file that passes extension check but has no valid speech
    minimal_wav = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
    resp = client.post(
        "/analyze",
        data={"text": "Emergency situation today!"},
        files={"audio": ("report.wav", minimal_wav, "audio/wav")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "currentness" in body
    # Text evidence should still flow through despite audio failure
    assert len(body["currentness"]["evidence"]) >= 1


# ---------------------------------------------------------------------------
# 7. /analyze — no modalities: 422 error
# ---------------------------------------------------------------------------

def test_analyze_no_modalities_returns_422():
    resp = client.post("/analyze", data={})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 8. /analyze — unsupported image type: 415 error
# ---------------------------------------------------------------------------

def test_analyze_unsupported_image_type_rejected():
    resp = client.post(
        "/analyze",
        data={"text": "Test"},
        files={"image": ("malware.exe", b"MZ\x90\x00", "application/octet-stream")},
    )
    assert resp.status_code == 415


# ---------------------------------------------------------------------------
# 9. /analyze — unsupported video type: 415 error
# ---------------------------------------------------------------------------

def test_analyze_unsupported_video_type_rejected():
    resp = client.post(
        "/analyze",
        data={"text": "Test"},
        files={"video": ("clip.xyz", b"\x00\x00\x00", "application/octet-stream")},
    )
    assert resp.status_code == 415


# ---------------------------------------------------------------------------
# 10. Combined response structure completeness
# ---------------------------------------------------------------------------

def test_combined_response_structure():
    resp = client.post("/analyze", data={"text": "Earthquake causing widespread damage right now!"})
    assert resp.status_code == 200
    body = resp.json()
    # Member 1 fields
    m1 = body["crisis_analysis"]
    for key in ("is_crisis", "incident_type", "information_type", "severity", "needs", "locations"):
        assert key in m1, f"Missing Member 1 field: {key}"
    # Member 2 fields
    c = body["currentness"]
    for key in ("currentness", "confidence", "action", "conflicts_detected", "evidence"):
        assert key in c, f"Missing Member 2 field: {key}"
    # Evidence items structure
    for ev in c["evidence"]:
        assert "source" in ev
        assert "polarity" in ev
        assert "weight" in ev
        assert "finding" in ev


# ---------------------------------------------------------------------------
# 11. HUMAN_VERIFICATION_REQUIRED exposed correctly
# ---------------------------------------------------------------------------

def test_uncertain_produces_human_verification_required():
    # Neutral / ambiguous text → likely UNCERTAIN
    resp = client.post(
        "/analyze",
        data={"text": "There was some incident somewhere."},
    )
    assert resp.status_code == 200
    c = resp.json()["currentness"]
    # When uncertain, action must be HUMAN_VERIFICATION_REQUIRED
    if c["currentness"] == "UNCERTAIN":
        assert c["action"] == "HUMAN_VERIFICATION_REQUIRED"


# ---------------------------------------------------------------------------
# 12. image-only (no text) is accepted
# ---------------------------------------------------------------------------

def test_image_only_no_text():
    resp = client.post(
        "/analyze",
        files={"image": ("scene.png", _png_bytes(color=(30, 90, 200)), "image/png")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "currentness" in body
    assert "crisis_analysis" in body
    # Member 1 cannot classify without text → all fields are None / empty
    m1 = body["crisis_analysis"]
    assert m1["is_crisis"] is None
    assert m1["severity"] is None
    assert m1["needs"] == []
    assert m1["locations"] == []
    # Member 2 should still attempt image evidence extraction
    assert isinstance(body["currentness"]["evidence"], list)


# ---------------------------------------------------------------------------
# 13. End-to-end OCR conflict detection with tesseract
# ---------------------------------------------------------------------------

def test_end_to_end_ocr_conflict_detection():
    # Render clear 2015 date on white background
    img = Image.new("RGB", (600, 150), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((30, 50), "DATE: 2015-04-25", fill="black")
    img_scaled = img.resize((1200, 300), Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    img_scaled.save(buf, format="PNG")
    buf.seek(0)

    resp = client.post(
        "/analyze",
        data={"text": "This fire is happening today."},
        files={"image": ("archive_2015.png", buf.read(), "image/png")},
    )
    assert resp.status_code == 200
    curr = resp.json()["currentness"]
    assert curr["currentness"] == "UNCERTAIN"
    assert curr["action"] == "HUMAN_VERIFICATION_REQUIRED"
    assert len(curr["conflicts_detected"]) > 0
    # Must have both CURRENT text evidence and OLD OCR evidence
    assert any(ev["source"] == "ocr" and ev["polarity"] == "OLD" for ev in curr["evidence"])
    assert any(ev["source"] == "text" and ev["polarity"] == "CURRENT" for ev in curr["evidence"])


# ---------------------------------------------------------------------------
# 14. Placeholder rejection test
# ---------------------------------------------------------------------------

def test_placeholder_submission_rejected():
    resp_text = client.post("/analyze-text", json={"text": "string"})
    assert resp_text.status_code == 422
    assert "placeholder" in resp_text.json()["detail"].lower()

    resp_form = client.post("/analyze", data={"text": "placeholder"})
    assert resp_form.status_code == 422
    assert "placeholder" in resp_form.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 15. Matching text and media evidence (no false conflict)
# ---------------------------------------------------------------------------

def test_matching_text_and_media_evidence_no_conflict():
    # When text is current and media does not have historical claims, no conflict is raised
    resp = client.post(
        "/analyze",
        data={"text": "Flash flood happening right now on Main Street!"},
        files={"image": ("flood_current.png", _png_bytes(), "image/png")},
    )
    assert resp.status_code == 200
    body = resp.json()
    curr = body["currentness"]
    # No conflict should be detected for matching / non-contradictory evidence
    assert len(curr["conflicts_detected"]) == 0
    assert body.get("has_conflict") is False


# ---------------------------------------------------------------------------
# 16. Database isolation test
# ---------------------------------------------------------------------------

def test_database_isolation_preserves_application_db():
    import sqlite3
    db_file = os.path.join(os.path.dirname(__file__), "..", "crisissense.db")
    if os.path.exists(db_file):
        conn = sqlite3.connect(db_file)
        # Verify database is readable and existing records are intact
        rep_count = conn.cursor().execute("SELECT COUNT(*) FROM reports").fetchone()[0]
        inc_count = conn.cursor().execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
        conn.close()
        assert rep_count >= 17
        assert inc_count >= 10


# ---------------------------------------------------------------------------
# 17. Missing modality test (image only without text form field)
# ---------------------------------------------------------------------------

def test_missing_modality_image_only():
    resp = client.post(
        "/analyze",
        files={"image": ("incident_only.png", _png_bytes(), "image/png")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "currentness" in body
    # Gracefully processed with missing text modality
    assert body["currentness"]["action"] in ("ALLOW", "HUMAN_VERIFICATION_REQUIRED")


# ---------------------------------------------------------------------------
# 18. Uncertain results require human verification
# ---------------------------------------------------------------------------

def test_uncertain_results_require_human_verification():
    # A generic statement without temporal markers produces UNCERTAIN verdict
    resp = client.post(
        "/analyze-text",
        json={"text": "Water levels rising near the riverbank in the residential district."},
    )
    assert resp.status_code == 200
    body = resp.json()
    curr = body["currentness"]
    assert curr["currentness"] == "UNCERTAIN"
    assert curr["action"] == "HUMAN_VERIFICATION_REQUIRED"


# ---------------------------------------------------------------------------
# 19. Conflicting evidence is preserved and routed to human review (not auto-rejected or auto-verified)
# ---------------------------------------------------------------------------

def test_conflicting_evidence_does_not_auto_reject_or_auto_verify():
    img = Image.new("RGB", (600, 150), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((30, 50), "PHOTO ARCHIVE 2014-06-12", fill="black")
    img_scaled = img.resize((1200, 300), Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    img_scaled.save(buf, format="PNG")
    buf.seek(0)

    resp = client.post(
        "/analyze",
        data={"text": "Building fire reported today right now on Oak Street!"},
        files={"image": ("archive_2014.png", buf.read(), "image/png")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_conflict"] is True
    assert len(body["conflicts_detected"]) > 0
    # Must NOT be confidently verified as CURRENT solely on text
    assert body["currentness"]["currentness"] != "CURRENT"
    assert body["currentness"]["action"] == "HUMAN_VERIFICATION_REQUIRED"
    # Must NOT be deleted or discarded
    assert body["storage_status"] in ("SAVED", "EXISTING_DUPLICATE")
    assert body["incident_id"] is not None



