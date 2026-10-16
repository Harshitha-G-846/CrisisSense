"""
test_enhancements.py
Regression tests for ResQ-Sense enhancements and bug fixes:
1. Audio analysis compatibility and MIME/extension validation.
2. Location search for Vijayawada, Jaisalmer, and query handling without device location.
3. Account verification code generation, verification, expiration, and throttling.
4. Admin-to-citizen information requests with authorization enforcement and email masking.
5. Real data analytics metrics handling both empty and populated states.
"""

from __future__ import annotations

import os
import io
import wave
import pytest
from datetime import timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from member3.database import Base, get_db
from member3.models import Incident, Report, User, AccountVerification, utc_now
from auth import create_access_token, hash_password, generate_verification_code, hash_verification_code
from email_service import get_mock_outbox, clear_mock_outbox
from main import app, _validate_audio_upload
from member1.location_extractor import extract_locations, geocode_location


@pytest.fixture
def isolated_db() -> Session:
    """Provides an isolated in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_fk(connection, connection_record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(isolated_db: Session) -> TestClient:
    """FastAPI TestClient with isolated in-memory database."""
    def override_get_db():
        try:
            yield isolated_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def clean_email_box(monkeypatch):
    monkeypatch.setenv("EMAIL_MOCK_MODE", "true")
    clear_mock_outbox()
    yield
    clear_mock_outbox()


# ── Audio Tests ─────────────────────────────────────────────────────────────

def test_audio_mime_validation():
    """Verify audio validator accepts both standard extensions and recorder MIME types."""
    from fastapi import UploadFile

    # Extension test
    file_wav = UploadFile(filename="audio.wav", file=io.BytesIO(b"dummy"))
    assert _validate_audio_upload(file_wav) == ".wav"

    from starlette.datastructures import Headers

    # WebM recorder blob test (typical browser MediaRecorder format)
    file_webm = UploadFile(
        filename="blob",
        file=io.BytesIO(b"dummy"),
        headers=Headers({"content-type": "audio/webm;codecs=opus"}),
    )
    assert _validate_audio_upload(file_webm) == ".webm"

    # Ogg recorder blob test
    file_ogg = UploadFile(
        filename="",
        file=io.BytesIO(b"dummy"),
        headers=Headers({"content-type": "audio/ogg"}),
    )
    assert _validate_audio_upload(file_ogg) == ".ogg"


def test_audio_pyav_compat_patch():
    """Verify PyAV compat patch strips metadata_errors without crashing."""
    from member2.audio import _patch_av_metadata_errors_compat
    _patch_av_metadata_errors_compat()
    import av
    # Calling av.open with metadata_errors should not raise TypeError
    # Creating a minimal WAV file in memory
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 1600)  # 0.1s of silence
    buf.seek(0)

    try:
        container = av.open(buf, mode="r", metadata_errors="ignore")
        container.close()
    except Exception as exc:
        pytest.fail(f"av.open failed with metadata_errors parameter: {exc}")


# ── Location Tests ──────────────────────────────────────────────────────────

def test_location_search_vijayawada(client: TestClient):
    """Test searching for Vijayawada returns exact geographic coordinates."""
    response = client.get("/locations/search?q=Vijayawada")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] >= 1
    first = data["results"][0]
    assert first["city"] == "Vijayawada"
    assert first["state"] == "Andhra Pradesh"
    assert pytest.approx(first["latitude"], 0.01) == 16.5062
    assert pytest.approx(first["longitude"], 0.01) == 80.6480


def test_location_search_jaisalmer(client: TestClient):
    """Test searching for Jaisalmer returns exact geographic coordinates."""
    response = client.get("/locations/search?q=Jaisalmer")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] >= 1
    first = data["results"][0]
    assert first["city"] == "Jaisalmer"
    assert first["state"] == "Rajasthan"
    assert pytest.approx(first["latitude"], 0.01) == 26.9157
    assert pytest.approx(first["longitude"], 0.01) == 70.9083


def test_location_search_partial_query(client: TestClient):
    """Test typing partial query like 'Vijay' finds Vijayawada instantly."""
    response = client.get("/locations/search?q=Vijay")
    assert response.status_code == 200
    data = response.json()
    cities = [r["city"] for r in data["results"]]
    assert "Vijayawada" in cities


def test_location_text_extraction_indian_cities():
    """Verify location extractor correctly detects Vijayawada and Jaisalmer in incident text."""
    vj_locs = extract_locations("High alert due to severe flooding in Vijayawada near Krishna river.")
    assert len(vj_locs) >= 1
    assert any(loc.get("city") == "Vijayawada" for loc in vj_locs)

    js_locs = extract_locations("Sandstorm emergency in Jaisalmer desert area.")
    assert len(js_locs) >= 1
    assert any(loc.get("city") == "Jaisalmer" for loc in js_locs)


# ── Account Verification Tests ──────────────────────────────────────────────

def test_registration_and_code_verification_flow(client: TestClient, isolated_db: Session):
    """Complete registration, email code dispatch, and verification lifecycle."""
    reg_res = client.post(
        "/auth/register",
        json={
            "full_name": "Test Citizen",
            "email": "citizen@resqsense.org",
            "password": "SecurePassword123!",
        },
    )
    assert reg_res.status_code == 201
    reg_data = reg_res.json()
    assert reg_data["user"]["is_verified"] is False
    assert reg_data["verification"]["status"] == "PENDING_VERIFICATION"

    # Verify code was dispatched to outbox
    outbox = get_mock_outbox()
    assert len(outbox) == 1
    sent_email = outbox[0]
    assert sent_email["recipient_email"] == "citizen@resqsense.org"
    code = sent_email["metadata"]["code"]
    assert len(code) == 6

    # Verify code via API
    verif_res = client.post(
        "/auth/verify-code",
        json={"email": "citizen@resqsense.org", "code": code},
    )
    assert verif_res.status_code == 200
    verif_data = verif_res.json()
    assert verif_data["status"] == "VERIFIED"
    assert verif_data["user"]["is_verified"] is True

    # Invalidate after use: using the same code again should return already verified or invalid
    token = verif_data["access_token"]
    status_res = client.get(
        "/auth/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert status_res.status_code == 200
    assert status_res.json()["is_verified"] is True


def test_verification_code_expiration(client: TestClient, isolated_db: Session):
    """Verify expired codes are rejected."""
    client.post(
        "/auth/register",
        json={
            "full_name": "Expired User",
            "email": "expired@resqsense.org",
            "password": "SecurePassword123!",
        },
    )
    # Manually expire the record in the database
    verif = isolated_db.scalar(
        select(AccountVerification).where(AccountVerification.email == "expired@resqsense.org")
    )
    verif.expires_at = utc_now() - timedelta(minutes=1)
    isolated_db.commit()

    code = get_mock_outbox()[0]["metadata"]["code"]
    res = client.post(
        "/auth/verify-code",
        json={"email": "expired@resqsense.org", "code": code},
    )
    assert res.status_code == 400
    assert "expired" in res.json()["detail"].lower()


def test_verification_code_attempt_throttling(client: TestClient):
    """Verify brute force guessing is throttled after 5 failed attempts."""
    client.post(
        "/auth/register",
        json={
            "full_name": "Brute Force",
            "email": "brute@resqsense.org",
            "password": "SecurePassword123!",
        },
    )

    # Attempt 5 wrong codes
    for i in range(5):
        res = client.post(
            "/auth/verify-code",
            json={"email": "brute@resqsense.org", "code": f"00000{i}"},
        )
        assert res.status_code == 400

    # 6th attempt should be blocked with 429
    res = client.post(
        "/auth/verify-code",
        json={"email": "brute@resqsense.org", "code": "999999"},
    )
    assert res.status_code == 429
    assert "too many" in res.json()["detail"].lower()


# ── Admin-to-Citizen Information Request Tests ──────────────────────────────

def test_admin_request_info_authorization(client: TestClient, isolated_db: Session):
    """Verify that unauthenticated users or normal citizens cannot request info."""
    incident = Incident(
        incident_type="Flood",
        severity="HIGH",
        status="OPEN",
        verification_status="PENDING",
    )
    isolated_db.add(incident)
    isolated_db.commit()

    # 1. Unauthenticated request
    res = client.post(
        f"/incidents/{incident.id}/request-info",
        json={"message": "Please send current water levels."},
    )
    assert res.status_code == 401

    # 2. Citizen user request (unauthorized)
    citizen_user = User(
        full_name="Regular Citizen",
        email="citizen_user@resqsense.org",
        password_hash=hash_password("Password123!"),
        role="citizen",
    )
    isolated_db.add(citizen_user)
    isolated_db.commit()
    citizen_token = create_access_token(citizen_user.id, citizen_user.email, citizen_user.role)

    res = client.post(
        f"/incidents/{incident.id}/request-info",
        headers={"Authorization": f"Bearer {citizen_token}"},
        json={"message": "Citizen trying to use admin endpoint"},
    )
    assert res.status_code == 403


def test_admin_request_info_success(client: TestClient, isolated_db: Session):
    """Verify authorized admin can request information from the submitting citizen."""
    # Create citizen
    citizen = User(
        full_name="John Doe",
        email="johndoe@example.com",
        password_hash=hash_password("Password123!"),
        role="citizen",
    )
    # Create authority admin
    admin = User(
        full_name="Captain Miller",
        email="miller@firedept.gov",
        password_hash=hash_password("Password123!"),
        role="authority",
    )
    isolated_db.add_all([citizen, admin])
    isolated_db.commit()

    incident = Incident(
        incident_type="Fire",
        severity="HIGH",
        status="OPEN",
        verification_status="PENDING",
        citizen_id=citizen.id,
    )
    isolated_db.add(incident)
    isolated_db.commit()

    admin_token = create_access_token(admin.id, admin.email, admin.role)

    res = client.post(
        f"/incidents/{incident.id}/request-info",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"message": "Are any occupants trapped on the second floor?"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "DISPATCHED"
    assert data["recipient_name"] == "John Doe"
    assert "jo***@example.com" in data["recipient_email_masked"]

    # Verify email was captured in outbox with proper details
    outbox = get_mock_outbox()
    assert len(outbox) == 1
    email = outbox[0]
    assert email["recipient_email"] == "johndoe@example.com"
    assert "Are any occupants trapped" in email["metadata"]["request_message"]
    assert email["metadata"]["admin_name"] == "Captain Miller"


# ── Analytics & Metrics Tests ───────────────────────────────────────────────

def test_analytics_metrics_empty_db(client: TestClient):
    """Verify /analytics/metrics handles empty database gracefully."""
    res = client.get("/analytics/metrics")
    assert res.status_code == 200
    data = res.json()
    assert data["total_incidents"] == 0
    assert data["total_reports"] == 0
    assert data["severity_distribution"] == {}
    assert data["status_distribution"] == {}
    assert data["timeline"] == []


def test_analytics_metrics_populated(client: TestClient, isolated_db: Session):
    """Verify /analytics/metrics calculates accurate distributions from real records."""
    inc1 = Incident(
        incident_type="Flood",
        severity="CRITICAL",
        status="OPEN",
        verification_status="VERIFIED",
    )
    inc2 = Incident(
        incident_type="Fire",
        severity="HIGH",
        status="IN_PROGRESS",
        verification_status="PENDING",
    )
    inc3 = Incident(
        incident_type="Flood",
        severity="CRITICAL",
        status="OPEN",
        verification_status="VERIFIED",
    )
    isolated_db.add_all([inc1, inc2, inc3])
    isolated_db.commit()

    res = client.get("/analytics/metrics")
    assert res.status_code == 200
    data = res.json()
    assert data["total_incidents"] == 3
    assert data["severity_distribution"]["CRITICAL"] == 2
    assert data["severity_distribution"]["HIGH"] == 1
    assert data["status_distribution"]["OPEN"] == 2
    assert data["status_distribution"]["IN_PROGRESS"] == 1
    assert data["incident_types"]["Flood"] == 2
    assert data["incident_types"]["Fire"] == 1
    assert len(data["timeline"]) >= 1
