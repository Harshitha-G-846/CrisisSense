"""
test_api_integration.py
Integration tests for the combined Member 1 + Member 2 FastAPI endpoints.
No network calls, no Whisper downloads, no external datasets.
"""

from __future__ import annotations

import io
import os
import numpy as np
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from main import app

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
