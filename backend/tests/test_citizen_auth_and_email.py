"""
test_citizen_auth_and_email.py
Unit and integration tests for citizen authentication, incident ownership,
access control, email confirmation dispatch, and schema backward-compatibility.

Uses isolated in-memory SQLite and mock email delivery; does NOT touch live crisissense.db.
"""

from __future__ import annotations

import os
import unittest.mock
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from member3.database import Base, get_db, ensure_schema_compatibility
from member3.models import Incident, Report, User
from auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    normalize_email,
    validate_password_strength,
)
from email_service import (
    send_incident_confirmation_email,
    get_mock_outbox,
    clear_mock_outbox,
)
from main import app


@pytest.fixture
def isolated_db() -> Generator[Session, None, None]:
    """Provides an isolated in-memory SQLite database."""
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
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def isolated_client(isolated_db: Session, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """TestClient wired to isolated in-memory database and mock email delivery."""
    monkeypatch.setenv("EMAIL_MOCK_MODE", "true")
    def _override_get_db():
        yield isolated_db

    clear_mock_outbox()
    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_db, None)
    clear_mock_outbox()


# ==============================================================================
# 1. Password Hashing and Input Validation Tests
# ==============================================================================

def test_password_hashing_security():
    """Verify strong salted password hashing with bcrypt."""
    password = "MyStrongPassword123!"
    pw_hash = hash_password(password)

    # Hash should be bcrypt format ($2b$)
    assert pw_hash.startswith("$2b$")
    assert pw_hash != password
    # Correct password verifies
    assert verify_password(password, pw_hash) is True
    # Incorrect password fails
    assert verify_password("WrongPassword123!", pw_hash) is False
    assert verify_password("", pw_hash) is False


def test_email_normalization():
    """Verify email normalization handles whitespace and case."""
    assert normalize_email("  Test.Citizen@Example.COM ") == "test.citizen@example.com"
    assert normalize_email("USER@DOMAIN.ORG") == "user@domain.org"


def test_password_strength_validation():
    """Verify password strength requirements (>=8 chars, letter + digit)."""
    # Valid
    validate_password_strength("ValidPass1")

    # Too short
    with pytest.raises(Exception):
        validate_password_strength("Short1")

    # Only letters
    with pytest.raises(Exception):
        validate_password_strength("AllLettersOnly")

    # Only numbers
    with pytest.raises(Exception):
        validate_password_strength("1234567890")


# ==============================================================================
# 2. Registration Tests
# ==============================================================================

def test_citizen_registration_success(isolated_client: TestClient, isolated_db: Session):
    """Test citizen registration creates user and returns safe profile with JWT."""
    payload = {
        "full_name": "Kavita Rao",
        "email": "kavita.rao@example.com",
        "password": "SecurePassword123!",
    }

    res = isolated_client.post("/auth/register", json=payload)
    assert res.status_code == 201
    data = res.json()

    assert "access_token" in data
    assert data["token_type"] == "bearer"
    user_data = data["user"]
    assert user_data["full_name"] == "Kavita Rao"
    assert user_data["email"] == "kavita.rao@example.com"
    assert user_data["role"] == "citizen"
    # Never expose password or hash in response
    assert "password" not in user_data
    assert "password_hash" not in user_data

    # Verify database state
    db_user = isolated_db.scalar(select(User).where(User.email == "kavita.rao@example.com"))
    assert db_user is not None
    assert db_user.full_name == "Kavita Rao"
    assert db_user.password_hash != "SecurePassword123!"
    assert verify_password("SecurePassword123!", db_user.password_hash)


def test_citizen_registration_duplicate_email(isolated_client: TestClient):
    """Test duplicate registration returns 409 Conflict."""
    payload = {
        "full_name": "Arjun Das",
        "email": "arjun.das@example.com",
        "password": "Password1234!",
    }

    res1 = isolated_client.post("/auth/register", json=payload)
    assert res1.status_code == 201

    # Attempt registration with same email (different case and trailing spaces)
    payload_dup = {
        "full_name": "Arjun Different Name",
        "email": "  ARJUN.DAS@EXAMPLE.COM  ",
        "password": "AnotherPassword456!",
    }
    res2 = isolated_client.post("/auth/register", json=payload_dup)
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"].lower() or "already registered" in res2.json()["detail"].lower()


def test_citizen_registration_invalid_inputs(isolated_client: TestClient):
    """Test validation errors for invalid registration inputs."""
    # Invalid email
    res1 = isolated_client.post("/auth/register", json={
        "full_name": "Bad Email User",
        "email": "not-an-email",
        "password": "ValidPassword123!",
    })
    assert res1.status_code in (400, 422)

    # Weak password
    res2 = isolated_client.post("/auth/register", json={
        "full_name": "Weak Pass User",
        "email": "weak@example.com",
        "password": "short",
    })
    assert res2.status_code in (400, 422)


# ==============================================================================
# 3. Login and Profile Tests
# ==============================================================================

def test_citizen_login_success_and_failures(isolated_client: TestClient):
    """Test citizen login flow with correct/incorrect credentials."""
    # Register first
    isolated_client.post("/auth/register", json={
        "full_name": "Vikram Seth",
        "email": "vikram@example.com",
        "password": "VikramPassword123!",
    })

    # Successful login
    res_ok = isolated_client.post("/auth/login", json={
        "email": "vikram@example.com",
        "password": "VikramPassword123!",
    })
    assert res_ok.status_code == 200
    token = res_ok.json()["access_token"]
    assert bool(token) is True

    # Failed login: incorrect password
    res_bad_pw = isolated_client.post("/auth/login", json={
        "email": "vikram@example.com",
        "password": "WrongPassword123!",
    })
    assert res_bad_pw.status_code == 401
    assert res_bad_pw.json()["detail"] == "Incorrect email or password."

    # Failed login: nonexistent user
    res_no_user = isolated_client.post("/auth/login", json={
        "email": "nonexistent@example.com",
        "password": "SomePassword123!",
    })
    assert res_no_user.status_code == 404
    assert res_no_user.json()["detail"] == "No account found with this email. Please register for a citizen account."


def test_citizen_profile_endpoint(isolated_client: TestClient):
    """Test GET /auth/me returns safe profile when authenticated."""
    reg = isolated_client.post("/auth/register", json={
        "full_name": "Meera Sen",
        "email": "meera@example.com",
        "password": "MeeraPassword123!",
    }).json()
    token = reg["access_token"]

    # Authorized profile fetch
    res_profile = isolated_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_profile.status_code == 200
    profile = res_profile.json()
    assert profile["full_name"] == "Meera Sen"
    assert profile["email"] == "meera@example.com"
    assert profile["role"] == "citizen"

    # Unauthorized profile fetch (no token)
    res_unauth = isolated_client.get("/auth/me")
    assert res_unauth.status_code == 401

    # Unauthorized profile fetch (invalid token)
    res_invalid = isolated_client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid.fake.token"},
    )
    assert res_invalid.status_code == 401


# ==============================================================================
# 4. Access Control Isolation Tests (Citizen vs Authority)
# ==============================================================================

def test_citizen_cannot_access_authority_endpoints(isolated_client: TestClient, isolated_db: Session):
    """Verify citizen token cannot perform authority-only operations (403 Forbidden)."""
    # Create incident
    inc = Incident(
        id="INC-AUTH-CHECK-1",
        incident_type="Flood",
        location_name="Assam",
        severity="HIGH",
        verification_status="PENDING",
        status="OPEN",
    )
    isolated_db.add(inc)
    isolated_db.commit()

    # Register citizen
    reg = isolated_client.post("/auth/register", json={
        "full_name": "Citizen User",
        "email": "citizen.access@example.com",
        "password": "CitizenPass123!",
    }).json()
    citizen_token = reg["access_token"]
    citizen_header = {"Authorization": f"Bearer {citizen_token}"}

    # 1. Verify endpoint
    res_verify = isolated_client.post(
        f"/incidents/{inc.id}/verify",
        json={"decision": "APPROVE", "reason": "Testing"},
        headers=citizen_header,
    )
    assert res_verify.status_code == 403
    assert "authority operations require administrator privileges" in res_verify.json()["detail"].lower()

    # 2. Authorize endpoint
    res_auth = isolated_client.post(
        f"/incidents/{inc.id}/authorize",
        headers=citizen_header,
    )
    assert res_auth.status_code == 403

    # 3. Replan endpoint
    res_replan = isolated_client.post(
        f"/incidents/{inc.id}/replan",
        headers=citizen_header,
    )
    assert res_replan.status_code == 403

    # 4. Update status endpoint
    res_status = isolated_client.patch(
        f"/incidents/{inc.id}/status",
        json={"status": "IN_PROGRESS"},
        headers=citizen_header,
    )
    assert res_status.status_code == 403

    # 5. Delete incident endpoint
    res_delete = isolated_client.delete(
        f"/incidents/{inc.id}",
        headers=citizen_header,
    )
    assert res_delete.status_code == 403


# ==============================================================================
# 5. Incident Ownership and Tracking Authorization Tests
# ==============================================================================

def test_authenticated_incident_submission_and_ownership(
    isolated_client: TestClient, isolated_db: Session
):
    """Test submitting incident while authenticated assigns citizen_id and outbox email."""
    reg = isolated_client.post("/auth/register", json={
        "full_name": "Deepak Joshi",
        "email": "deepak.joshi@example.com",
        "password": "DeepakPassword123!",
    }).json()
    token = reg["access_token"]
    user_id = reg["user"]["id"]

    # Submit incident with citizen token
    clear_mock_outbox()
    res = isolated_client.post(
        "/analyze-text",
        json={"text": "Massive urban flood near Silchar hospital, water rising rapidly."},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    incident_id = data["incident_id"]
    report_id = data["report_id"]
    assert incident_id is not None
    assert report_id is not None
    assert data["storage_status"] == "SAVED"

    # Verify ownership in database
    db_incident = isolated_db.get(Incident, incident_id)
    assert db_incident.citizen_id == user_id
    db_report = isolated_db.get(Report, report_id)
    assert db_report.citizen_id == user_id

    # Verify confirmation email in mock outbox
    outbox = get_mock_outbox()
    assert len(outbox) == 1
    email = outbox[0]
    assert email["recipient"] == "deepak.joshi@example.com"
    assert incident_id in email["text_content"]
    assert "localhost" not in email["text_content"]
    assert "localhost" not in email["html_body"]
    assert "http://" not in email["text_content"]
    assert "http://" not in email["html_body"]
    assert email.get("tracking_url") == ""


def test_incident_tracking_access_control(
    isolated_client: TestClient, isolated_db: Session
):
    """Test that only owning citizen or authority can view private incident details."""
    # Register Citizen A
    user_a = isolated_client.post("/auth/register", json={
        "full_name": "Citizen A",
        "email": "citizena@example.com",
        "password": "Password123!",
    }).json()
    token_a = user_a["access_token"]

    # Register Citizen B
    user_b = isolated_client.post("/auth/register", json={
        "full_name": "Citizen B",
        "email": "citizenb@example.com",
        "password": "Password123!",
    }).json()
    token_b = user_b["access_token"]

    # Citizen A submits an incident
    sub = isolated_client.post(
        "/analyze-text",
        json={"text": "Cyclone damage on coast road, electric poles down."},
        headers={"Authorization": f"Bearer {token_a}"},
    ).json()
    incident_id = sub["incident_id"]

    # 1. Citizen A (owner) can view their incident
    res_owner = isolated_client.get(
        f"/incidents/{incident_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res_owner.status_code == 200
    assert res_owner.json()["incident_id"] == incident_id

    # 2. Citizen B (non-owner) cannot view Citizen A's incident (404)
    res_other = isolated_client.get(
        f"/incidents/{incident_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res_other.status_code == 404
    assert "unauthorized" in res_other.json()["detail"].lower()

    # 3. Unauthenticated request cannot view Citizen A's incident (404)
    res_anon = isolated_client.get(f"/incidents/{incident_id}")
    assert res_anon.status_code == 404

    # 4. Authority operator can view Citizen A's incident
    # Create authority user
    auth_user = User(
        id="usr-auth-op-1",
        full_name="Chief Coordinator",
        email="coordinator@resqsense.gov",
        password_hash=hash_password("AdminPass123!"),
        role="authority",
    )
    isolated_db.add(auth_user)
    isolated_db.commit()

    auth_token = create_access_token(user_id=auth_user.id, email=auth_user.email, role="authority")
    res_authority = isolated_client.get(
        f"/incidents/{incident_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert res_authority.status_code == 200
    assert res_authority.json()["incident_id"] == incident_id
    assert res_authority.json()["submitting_citizen"] is not None
    assert res_authority.json()["submitting_citizen"]["email"] == "citizena@example.com"
    assert res_authority.json()["submitting_citizen"]["full_name"] == "Citizen A"
    assert res_authority.json()["submitting_citizen"]["is_anonymous"] is False


def test_legacy_unowned_incidents_remain_accessible(
    isolated_client: TestClient, isolated_db: Session
):
    """Test backward compatibility: unowned legacy incidents are accessible to operators, but hidden from unauthorized citizens."""
    legacy_inc = Incident(
        id="INC-LEGACY-001",
        incident_type="Fire",
        location_name="Old Delhi",
        severity="MEDIUM",
        citizen_id=None,  # Legacy record with no owner
        verification_status="VERIFIED",
        status="OPEN",
    )
    isolated_db.add(legacy_inc)
    isolated_db.commit()

    # Unauthenticated / unauthorized lookup returns 404
    res_unauth = isolated_client.get(f"/incidents/{legacy_inc.id}")
    assert res_unauth.status_code == 404

    # Authority operator can view the legacy incident
    admin_user = User(
        id="usr-legacy-admin",
        full_name="Legacy Operator",
        email="admin.legacy@resqsense.gov",
        password_hash=hash_password("Pass123!"),
        role="authority",
    )
    isolated_db.add(admin_user)
    isolated_db.commit()
    admin_token = create_access_token(user_id=admin_user.id, email=admin_user.email, role="authority")
    res_auth = isolated_client.get(
        f"/incidents/{legacy_inc.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_auth.status_code == 200
    assert res_auth.json()["incident_id"] == legacy_inc.id
    assert res_auth.json()["submitting_citizen"] is not None
    assert res_auth.json()["submitting_citizen"]["full_name"] == "Anonymous submission"
    assert res_auth.json()["submitting_citizen"]["email"] == "No linked citizen account"
    assert res_auth.json()["submitting_citizen"]["is_anonymous"] is True


def test_citizen_registration_cannot_grant_admin_role(isolated_client: TestClient):
    """Test that public registration cannot create an administrator or authority account."""
    # Attempt privilege escalation via registration payload
    res = isolated_client.post("/auth/register", json={
        "full_name": "Hacker User",
        "email": "hacker@example.com",
        "password": "HackerPassword123!",
        "role": "admin",
    })
    assert res.status_code == 201
    user_data = res.json()["user"]
    # Role MUST be citizen regardless of requested role
    assert user_data["role"] == "citizen"

    # Profile check verifies citizen role persisted
    token = res.json()["access_token"]
    profile = isolated_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert profile["role"] == "citizen"


def test_new_citizen_has_zero_incidents_isolated(
    isolated_client: TestClient, isolated_db: Session
):
    """Test that a newly registered citizen sees strictly 0 incidents and cannot see other citizens' data."""
    # Register Citizen 1
    c1 = isolated_client.post("/auth/register", json={
        "full_name": "Citizen One",
        "email": "citizen1@example.com",
        "password": "Password123!",
    }).json()
    token1 = c1["access_token"]

    # Register Citizen 2
    c2 = isolated_client.post("/auth/register", json={
        "full_name": "Citizen Two",
        "email": "citizen2@example.com",
        "password": "Password123!",
    }).json()
    token2 = c2["access_token"]

    # Citizen 1 has zero incidents initially
    res_list1_init = isolated_client.get("/citizen/incidents", headers={"Authorization": f"Bearer {token1}"})
    assert res_list1_init.status_code == 200
    assert res_list1_init.json() == []

    # Citizen 2 has zero incidents initially
    res_list2_init = isolated_client.get("/citizen/incidents", headers={"Authorization": f"Bearer {token2}"})
    assert res_list2_init.status_code == 200
    assert res_list2_init.json() == []

    # Citizen 1 submits an incident
    sub1 = isolated_client.post(
        "/analyze-text",
        json={"text": "Flood water entering ground floor in Guwahati sector 4."},
        headers={"Authorization": f"Bearer {token1}"},
    ).json()
    inc1_id = sub1["incident_id"]

    # Citizen 1 now sees exactly 1 incident
    res_list1 = isolated_client.get("/citizen/incidents", headers={"Authorization": f"Bearer {token1}"})
    assert res_list1.status_code == 200
    items1 = res_list1.json()
    assert len(items1) == 1
    assert items1[0]["incident_id"] == inc1_id

    # Citizen 2 still sees 0 incidents (strict data isolation)
    res_list2 = isolated_client.get("/citizen/incidents", headers={"Authorization": f"Bearer {token2}"})
    assert res_list2.status_code == 200
    assert res_list2.json() == []

    # Citizen 2 cannot track Citizen 1's incident directly (404)
    res_track2 = isolated_client.get(f"/incidents/{inc1_id}", headers={"Authorization": f"Bearer {token2}"})
    assert res_track2.status_code == 404


def test_unauthenticated_cannot_access_authority_or_citizen_endpoints(
    isolated_client: TestClient
):
    """Test unauthenticated visitors are rejected with 401 on protected endpoints."""
    # Authority incidents list requires authentication
    res_authority_incidents = isolated_client.get("/incidents")
    assert res_authority_incidents.status_code == 401

    # Citizen personal incidents list requires authentication
    res_citizen_incidents = isolated_client.get("/citizen/incidents")
    assert res_citizen_incidents.status_code == 401

    # Public stats is accessible without authentication
    res_stats = isolated_client.get("/public/stats")
    assert res_stats.status_code == 200
    assert "monitored_incidents" in res_stats.json()


def test_admin_login_endpoint(
    isolated_client: TestClient, isolated_db: Session
):
    """Test dedicated administrator login workflow, authorization, and error cases."""
    # Create an authorized administrator user in DB
    admin_user = User(
        id="usr-super-admin-1",
        full_name="Emergency Director",
        email="director@resqsense.gov",
        password_hash=hash_password("SuperSecretAdminPass123!"),
        role="authority",
    )
    isolated_db.add(admin_user)
    isolated_db.commit()

    # 1. Valid administrator login succeeds
    res_admin_login = isolated_client.post("/auth/admin/login", json={
        "email": "director@resqsense.gov",
        "password": "SuperSecretAdminPass123!",
    })
    assert res_admin_login.status_code == 200
    admin_token = res_admin_login.json()["access_token"]
    assert res_admin_login.json()["user"]["role"] == "authority"

    # Administrator token can access authority endpoints
    res_incidents = isolated_client.get("/incidents", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_incidents.status_code == 200

    # 2. Invalid administrator password fails (401)
    res_bad_pw = isolated_client.post("/auth/admin/login", json={
        "email": "director@resqsense.gov",
        "password": "WrongPassword123!",
    })
    assert res_bad_pw.status_code == 401

    # 3. Unknown administrator email fails (401)
    res_unknown = isolated_client.post("/auth/admin/login", json={
        "email": "unknown.admin@resqsense.gov",
        "password": "WrongPassword123!",
    })
    assert res_unknown.status_code == 401

    # 4. Citizen credentials passed to admin login are rejected (403 Forbidden)
    c_reg = isolated_client.post("/auth/register", json={
        "full_name": "Regular Citizen",
        "email": "regular.citizen@example.com",
        "password": "RegularCitizenPass123!",
    }).json()
    citizen_token = c_reg["access_token"]

    res_citizen_try_admin = isolated_client.post("/auth/admin/login", json={
        "email": "regular.citizen@example.com",
        "password": "RegularCitizenPass123!",
    })
    assert res_citizen_try_admin.status_code == 403
    assert "administrator privileges" in res_citizen_try_admin.json()["detail"].lower()

    # Citizen token cannot access authority list endpoint (403)
    res_citizen_list = isolated_client.get("/incidents", headers={"Authorization": f"Bearer {citizen_token}"})
    assert res_citizen_list.status_code == 403


# ==============================================================================
# 6. Email Service Tests (Mock Mode & Delivery Failure Handling)
# ==============================================================================

def test_email_service_mock_mode_outbox():
    """Verify confirmation email creation, formatting, and mock outbox capture."""
    clear_mock_outbox()

    result = send_incident_confirmation_email(
        recipient_email="alert.citizen@example.com",
        citizen_name="Sanjay Gupta",
        incident_id="INC-OUTBOX-999",
        incident_type="Flood",
        location_name="Guwahati",
        submission_timestamp="2026-10-14T10:30:00Z",
        mock_mode_override=True,
    )

    assert result.status == "MOCKED"
    assert result.recipient == "alert.citizen@example.com"
    assert result.subject == "ResQ-Sense: Incident submitted successfully"
    assert result.tracking_url == ""

    outbox = get_mock_outbox()
    assert len(outbox) == 1
    recorded = outbox[0]
    assert recorded["incident_id"] == "INC-OUTBOX-999"
    assert "Sanjay Gupta" in recorded["text_content"]
    assert "ResQ-Sense" in recorded["text_content"]
    assert recorded["incident_id"] in recorded["text_content"]
    assert "localhost" not in recorded["text_content"]
    assert "localhost" not in recorded["html_body"]
    clear_mock_outbox()


def test_email_service_failure_does_not_break_incident_persistence(
    isolated_client: TestClient, isolated_db: Session
):
    """Verify that SMTP failure is reported gracefully and incident remains safely persisted."""
    reg = isolated_client.post("/auth/register", json={
        "full_name": "Failure Test User",
        "email": "failtest@example.com",
        "password": "Password123!",
    }).json()
    token = reg["access_token"]

    # Mock send_incident_confirmation_email to simulate an SMTP connection error
    with unittest.mock.patch("main.send_incident_confirmation_email") as mock_send:
        from email_service import EmailDeliveryResult
        mock_send.return_value = EmailDeliveryResult(
            status="FAILED",
            recipient="failtest@example.com",
            subject="ResQ-Sense: Incident submitted successfully",
            message="SMTP delivery failed",
            tracking_url="http://localhost:5173/?view=citizen-status&incident_id=INC-FAIL",
            error="Connection refused to SMTP server",
        )

        res = isolated_client.post(
            "/analyze-text",
            json={"text": "Landslide blocking mountain pass road in Uttarakhand."},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert res.status_code == 200
        data = res.json()
        assert data["storage_status"] == "SAVED"
        assert data["incident_id"] is not None
        # Email status indicates delivery failed, but submission succeeded!
        assert data["email_notification"]["status"] == "FAILED"
        assert "Connection refused" in data["email_notification"]["error"]

        # Verify incident is in database
        inc = isolated_db.get(Incident, data["incident_id"])
        assert inc is not None


# ==============================================================================
# 7. Non-Destructive Schema Compatibility Test
# ==============================================================================

def test_non_destructive_schema_compatibility():
    """Verify ensure_schema_compatibility adds citizen_id without dropping existing records."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        # Create legacy schema without citizen_id
        conn.exec_driver_sql(
            "CREATE TABLE incidents (id TEXT PRIMARY KEY, incident_type TEXT, location_name TEXT, created_at DATETIME, updated_at DATETIME)"
        )
        conn.exec_driver_sql(
            "CREATE TABLE reports (id TEXT PRIMARY KEY, original_text TEXT, received_at DATETIME)"
        )
        conn.exec_driver_sql(
            "INSERT INTO incidents (id, incident_type, location_name) VALUES ('INC-PRESERVED', 'Flood', 'Assam')"
        )

    # Run non-destructive compatibility update
    ensure_schema_compatibility(engine)

    with engine.begin() as conn:
        # Verify legacy record was preserved
        row = conn.exec_driver_sql("SELECT id, incident_type, citizen_id FROM incidents WHERE id = 'INC-PRESERVED'").fetchone()
        assert row[0] == "INC-PRESERVED"
        assert row[1] == "Flood"
        assert row[2] is None  # new column added safely!

        # Verify users table exists
        tables = conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").scalars().all()
        assert "users" in tables

    engine.dispose()


def test_ensure_schema_compatibility_default_argument():
    """Verify ensure_schema_compatibility() can be called with no arguments safely without TypeError."""
    # Calling with no arguments uses default target_engine=None -> engine
    ensure_schema_compatibility()


def test_provision_admin_script_logic(isolated_db: Session):
    """Verify provision_admin script provisions admin, uses bcrypt hash, and prevents duplicate records."""
    from scripts.create_admin import provision_admin

    # 1. Provision new administrator
    admin = provision_admin(
        email="commander@resqsense.gov",
        password="CommanderPassword123!",
        name="Duty Commander",
        role="authority",
        db_session=isolated_db,
    )
    assert admin is not None
    assert admin.email == "commander@resqsense.gov"
    assert admin.role == "authority"
    assert verify_password("CommanderPassword123!", admin.password_hash) is True

    # Exactly 1 user in isolated DB
    assert isolated_db.query(User).count() == 1

    # 2. Re-provisioning the same email updates existing account without creating duplicate
    updated_admin = provision_admin(
        email="commander@resqsense.gov",
        password="NewCommanderPassword456!",
        name="Senior Duty Commander",
        role="authority",
        db_session=isolated_db,
    )
    assert updated_admin.id == admin.id
    assert updated_admin.full_name == "Senior Duty Commander"
    assert verify_password("NewCommanderPassword456!", updated_admin.password_hash) is True

    # User count is strictly 1 (no duplicate)
    assert isolated_db.query(User).count() == 1
