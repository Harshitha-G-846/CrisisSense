"""
test_incident_deletion.py
Comprehensive tests for permanent incident deletion:
1. Successful incident deletion via DELETE /incidents/{incident_id}.
2. 404 Not Found response when deleting nonexistent incident ID.
3. Safe cascading deletion of linked reports without leaving orphaned records.
4. Preserving unrelated incidents, other reports, and unassigned reports.
5. Deletion of an incident with zero linked reports.
6. Incident list (GET /incidents) reflects deletion immediately.
7. Foreign key enforcement with PRAGMA foreign_keys=ON in SQLite.
8. Direct incident_service.delete_incident function verification.
9. Zero modification of persistent crisissense.db.
"""

from __future__ import annotations

import os
import sqlite3
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from member3.database import Base, get_db
from member3.models import Incident, Report, User
from member3.incident_service import delete_incident
from auth import create_access_token, hash_password
from main import app

# Snapshot live database state when the test module loads to detect any unwanted test writes
_DB_PATH = "backend/crisissense.db" if os.path.exists("backend/crisissense.db") else "crisissense.db"
_INITIAL_COUNTS = {}
if os.path.exists(_DB_PATH):
    try:
        _conn = sqlite3.connect(_DB_PATH)
        _INITIAL_COUNTS = {
            t: _conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ["incidents", "reports", "resources", "users"]
        }
        _conn.close()
    except Exception:
        pass


@pytest.fixture
def isolated_db() -> Generator[Session, None, None]:
    """Provides an isolated in-memory SQLite database with foreign keys enabled."""
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
def isolated_client(isolated_db: Session) -> Generator[TestClient, None, None]:
    """TestClient that uses the isolated in-memory database."""
    def _override_get_db():
        yield isolated_db

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def auth_header(isolated_db: Session) -> dict:
    """Fixture providing authorized authority credentials."""
    admin = User(
        id="usr-del-admin",
        full_name="Deletion Admin",
        email="admin.del@resqsense.gov",
        password_hash=hash_password("AdminPass123!"),
        role="authority",
    )
    isolated_db.add(admin)
    isolated_db.commit()
    token = create_access_token(user_id=admin.id, email=admin.email, role="authority")
    return {"Authorization": f"Bearer {token}"}


def test_successful_incident_deletion(
    isolated_client: TestClient, isolated_db: Session, auth_header: dict
):
    """Test that DELETE /incidents/{id} successfully removes the incident."""
    inc = Incident(
        id="INC-DEL-TEST-001",
        incident_type="Flood",
        location_name="Guwahati",
        severity="HIGH",
        needs=["rescue", "water"],
        verification_status="PENDING",
        status="OPEN",
    )
    isolated_db.add(inc)
    isolated_db.commit()

    # Verify incident exists
    assert isolated_db.get(Incident, "INC-DEL-TEST-001") is not None

    # Call DELETE endpoint with authority credentials
    resp = isolated_client.delete("/incidents/INC-DEL-TEST-001", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["incident_id"] == "INC-DEL-TEST-001"
    assert "permanently deleted" in data["message"].lower()

    # Verify incident is deleted from DB
    assert isolated_db.get(Incident, "INC-DEL-TEST-001") is None


def test_delete_nonexistent_incident_returns_404(
    isolated_client: TestClient, auth_header: dict
):
    """Test that DELETE /incidents/{id} returns 404 for a nonexistent ID."""
    resp = isolated_client.delete("/incidents/INC-NONEXISTENT-999", headers=auth_header)
    assert resp.status_code == 404
    data = resp.json()
    assert "detail" in data
    assert "Incident not found" in data["detail"]


def test_cascade_deletion_removes_linked_reports_and_preserves_unrelated(
    isolated_client: TestClient, isolated_db: Session, auth_header: dict
):
    """
    Test that deleting an incident:
    - Permanently deletes all linked reports (no orphaned records).
    - Preserves all other incidents and their reports completely intact.
    - Preserves unassigned reports.
    """
    # Incident 1 (Target for deletion)
    inc1 = Incident(
        id="INC-CASCADE-TARGET",
        incident_type="Cyclone",
        location_name="Chennai",
        severity="CRITICAL",
        verification_status="VERIFIED",
        status="OPEN",
    )
    # Incident 2 (Should remain untouched)
    inc2 = Incident(
        id="INC-PRESERVE-OTHER",
        incident_type="Earthquake",
        location_name="Shillong",
        severity="MEDIUM",
        verification_status="PENDING",
        status="OPEN",
    )
    isolated_db.add_all([inc1, inc2])
    isolated_db.flush()

    # Reports for Incident 1
    rep1 = Report(
        id="REP-TARGET-001",
        incident_id=inc1.id,
        original_text="Severe winds tearing down roofs in Chennai",
        crisis_analysis={"incident_type": "Cyclone", "severity": "CRITICAL"},
        currentness_assessment={"currentness": "CURRENT", "confidence": 0.95},
    )
    rep2 = Report(
        id="REP-TARGET-002",
        incident_id=inc1.id,
        original_text="Flooding on Marina Beach road",
        crisis_analysis={"incident_type": "Cyclone", "severity": "HIGH"},
        currentness_assessment={"currentness": "CURRENT", "confidence": 0.88},
    )
    # Report for Incident 2
    rep3 = Report(
        id="REP-OTHER-001",
        incident_id=inc2.id,
        original_text="Tremors felt in Shillong hills",
        crisis_analysis={"incident_type": "Earthquake", "severity": "MEDIUM"},
        currentness_assessment={"currentness": "CURRENT", "confidence": 0.90},
    )
    # Unassigned Report (no incident)
    rep4 = Report(
        id="REP-UNASSIGNED-001",
        incident_id=None,
        original_text="General weather warning",
        crisis_analysis={"incident_type": "Weather", "is_crisis": False},
        currentness_assessment={"currentness": "CURRENT", "confidence": 0.70},
    )

    isolated_db.add_all([rep1, rep2, rep3, rep4])
    isolated_db.commit()

    # Pre-conditions
    assert isolated_db.query(Incident).count() == 2
    assert isolated_db.query(Report).count() == 4

    # Delete Incident 1
    resp = isolated_client.delete(f"/incidents/{inc1.id}", headers=auth_header)
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # Verification:
    # 1. Target Incident is deleted
    assert isolated_db.get(Incident, inc1.id) is None

    # 2. Linked reports for Target Incident are deleted (no orphaned reports)
    assert isolated_db.get(Report, rep1.id) is None
    assert isolated_db.get(Report, rep2.id) is None

    # 3. Unrelated Incident 2 is completely preserved
    stored_inc2 = isolated_db.get(Incident, inc2.id)
    assert stored_inc2 is not None
    assert stored_inc2.incident_type == "Earthquake"
    assert stored_inc2.location_name == "Shillong"

    # 4. Report for Incident 2 is completely preserved and still linked
    stored_rep3 = isolated_db.get(Report, rep3.id)
    assert stored_rep3 is not None
    assert stored_rep3.incident_id == inc2.id

    # 5. Unassigned report is completely preserved
    stored_rep4 = isolated_db.get(Report, rep4.id)
    assert stored_rep4 is not None
    assert stored_rep4.incident_id is None

    # Final counts
    assert isolated_db.query(Incident).count() == 1
    assert isolated_db.query(Report).count() == 2


def test_delete_incident_with_zero_reports(
    isolated_client: TestClient, isolated_db: Session, auth_header: dict
):
    """Test deleting an incident that has no associated reports."""
    inc = Incident(
        id="INC-ZERO-REPORTS",
        incident_type="Fire",
        location_name="Warehouse 4",
        severity="LOW",
        verification_status="PENDING",
        status="OPEN",
    )
    isolated_db.add(inc)
    isolated_db.commit()

    resp = isolated_client.delete(f"/incidents/{inc.id}", headers=auth_header)
    assert resp.status_code == 200
    assert isolated_db.get(Incident, inc.id) is None


def test_incidents_list_reflects_deletion_immediately(
    isolated_client: TestClient, isolated_db: Session, auth_header: dict
):
    """Test that GET /incidents immediately reflects the deletion."""
    inc1 = Incident(id="INC-LIST-A", incident_type="Flood", severity="HIGH")
    inc2 = Incident(id="INC-LIST-B", incident_type="Fire", severity="LOW")
    isolated_db.add_all([inc1, inc2])
    isolated_db.commit()

    # List before deletion
    list_resp = isolated_client.get("/incidents", headers=auth_header)
    assert list_resp.status_code == 200
    ids_before = [item["incident_id"] for item in list_resp.json()]
    assert "INC-LIST-A" in ids_before
    assert "INC-LIST-B" in ids_before

    # Delete inc1
    del_resp = isolated_client.delete("/incidents/INC-LIST-A", headers=auth_header)
    assert del_resp.status_code == 200

    # List after deletion
    list_resp2 = isolated_client.get("/incidents", headers=auth_header)
    assert list_resp2.status_code == 200
    ids_after = [item["incident_id"] for item in list_resp2.json()]
    assert "INC-LIST-A" not in ids_after
    assert "INC-LIST-B" in ids_after

    # Detail of deleted incident returns 404
    detail_resp = isolated_client.get("/incidents/INC-LIST-A", headers=auth_header)
    assert detail_resp.status_code == 404


def test_delete_incident_unauthenticated_and_citizen_denied(
    isolated_client: TestClient, isolated_db: Session
):
    """Test that DELETE /incidents/{id} requires authority credentials."""
    inc = Incident(id="INC-AUTH-DENIED-DEL", incident_type="Flood", severity="HIGH")
    isolated_db.add(inc)
    isolated_db.commit()

    # 1. Unauthenticated DELETE returns 401
    res_unauth = isolated_client.delete(f"/incidents/{inc.id}")
    assert res_unauth.status_code == 401

    # 2. Citizen token DELETE returns 403
    citizen_user = User(
        id="usr-cit-denied",
        full_name="Citizen Del Denied",
        email="cit.del@example.com",
        password_hash=hash_password("CitizenPass123!"),
        role="citizen",
    )
    isolated_db.add(citizen_user)
    isolated_db.commit()
    citizen_token = create_access_token(user_id=citizen_user.id, email=citizen_user.email, role="citizen")

    res_citizen = isolated_client.delete(
        f"/incidents/{inc.id}",
        headers={"Authorization": f"Bearer {citizen_token}"},
    )
    assert res_citizen.status_code == 403


def test_direct_delete_incident_service_function(isolated_db: Session):
    """Test the Python incident_service.delete_incident function directly."""
    inc = Incident(id="INC-SERVICE-TEST", incident_type="Storm")
    isolated_db.add(inc)
    isolated_db.commit()

    # Existing incident deletion returns True
    success = delete_incident(isolated_db, "INC-SERVICE-TEST")
    assert success is True
    assert isolated_db.get(Incident, "INC-SERVICE-TEST") is None

    # Deleting again / nonexistent ID returns False
    success_again = delete_incident(isolated_db, "INC-SERVICE-TEST")
    assert success_again is False

    nonexistent_success = delete_incident(isolated_db, "INC-NEVER-EXISTED")
    assert nonexistent_success is False


def test_crisissense_db_strictly_untouched():
    """Verify that tests strictly execute in-memory and never write to or delete from crisissense.db."""
    db_path = "backend/crisissense.db" if os.path.exists("backend/crisissense.db") else "crisissense.db"
    if not os.path.exists(db_path):
        pytest.skip("crisissense.db not found")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 1. Verify counts before and after the test run are 100% identical
    final_counts = {
        t: cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ["incidents", "reports", "resources", "users"]
    }

    # 2. Verify no test artifacts exist in the persistent database
    test_incident_ids = [
        "INC-DEL-TEST-001",
        "INC-CASCADE-TEST",
        "INC-UNRELATED-KEEP",
        "INC-ZERO-REPORTS",
        "INC-GUARD-TEST",
        "INC-SERVICE-TEST",
        "INC-NEVER-EXISTED",
    ]
    found_test_incidents = cur.execute(
        f"SELECT id FROM incidents WHERE id IN ({','.join('?' for _ in test_incident_ids)})",
        test_incident_ids,
    ).fetchall()

    test_report_ids = ["REP-CASCADE-001", "REP-CASCADE-002", "REP-UNRELATED-999"]
    found_test_reports = cur.execute(
        f"SELECT id FROM reports WHERE id IN ({','.join('?' for _ in test_report_ids)})",
        test_report_ids,
    ).fetchall()

    test_user_ids = ["usr-del-admin", "cit.del@example.com"]
    found_test_users = cur.execute(
        f"SELECT id FROM users WHERE id IN ({','.join('?' for _ in test_user_ids)})",
        test_user_ids,
    ).fetchall()

    conn.close()

    assert found_test_incidents == [], f"Test incidents leaked into live DB: {found_test_incidents}"
    assert found_test_reports == [], f"Test reports leaked into live DB: {found_test_reports}"
    assert found_test_users == [], f"Test users leaked into live DB: {found_test_users}"

    if _INITIAL_COUNTS:
        assert final_counts == _INITIAL_COUNTS, (
            f"crisissense.db was modified during test run! Initial: {_INITIAL_COUNTS}, Final: {final_counts}"
        )

