"""
test_needs_more_info_email.py - Comprehensive Unit & Integration Tests for
ResQ-Sense Admin Feedback Email Notification on "Needs More Info" Workflow.

Validates:
1. Valid citizen recipient: resolves email via authenticated incident ownership or linked report;
   dispatches email with subject "Additional Information Required — ResQ-Sense Incident",
   reference ID, category, location, admin feedback, and sign-in instructions.
2. Missing email address (anonymous submission): saves feedback and status in DB,
   reports email_sent=False and email_status="NO_RECIPIENT" without crashing.
3. SMTP delivery failure: saves status and feedback in DB reliably, reports
   email_sent=False and email_status="FAILED" with error details (no silent failure).
4. Other verification decisions (APPROVE, REJECT): do NOT trigger email notifications.
5. In-app feedback visibility: admin_feedback is serialized in verify response,
   GET /incidents/{id}, and GET /citizen/incidents.
"""

from __future__ import annotations

import os
import unittest.mock
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from member3.database import Base, get_db
from member3.models import Incident, Report, User
from member4.verification_service import verify_incident, _mask_email
from email_service import (
    get_mock_outbox,
    clear_mock_outbox,
    send_needs_more_info_email,
    EmailDeliveryResult,
)
from auth import hash_password, create_access_token
from main import app


@pytest.fixture
def test_db() -> Generator[Session, None, None]:
    """Isolated in-memory SQLite database for testing."""
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


@pytest.fixture
def sample_users(test_db: Session) -> dict[str, User]:
    """Create authority and citizen test users."""
    admin = User(
        id="USER-admin-01",
        full_name="Commander Shepard",
        email="commander.shepard@authority.gov",
        password_hash=hash_password("Pass1234!"),
        role="authority",
    )
    citizen = User(
        id="USER-citizen-01",
        full_name="Jane Doe",
        email="jane.doe@example.org",
        password_hash=hash_password("Pass1234!"),
        role="citizen",
    )
    other_citizen = User(
        id="USER-citizen-02",
        full_name="Bob Smith",
        email="bob.smith@example.org",
        password_hash=hash_password("Pass1234!"),
        role="citizen",
    )
    test_db.add_all([admin, citizen, other_citizen])
    test_db.commit()
    return {"admin": admin, "citizen": citizen, "other": other_citizen}


class TestNeedsMoreInfoEmailWorkflow:
    def test_mask_email_utility(self):
        """Verify email privacy masking utility."""
        assert _mask_email("jane.doe@example.org") == "j******e@example.org"
        assert _mask_email("a@b.com") == "a*@b.com"
        assert _mask_email("") == ""
        assert _mask_email("invalid-no-at") == "invalid-no-at"

    def test_needs_more_info_email_sent_to_authenticated_owner(
        self, test_db: Session, sample_users: dict[str, User]
    ):
        """When an admin selects Needs More Info, the authenticated citizen receives an email."""
        clear_mock_outbox()
        citizen = sample_users["citizen"]
        admin = sample_users["admin"]

        inc = Incident(
            id="INC-test-valid-01",
            incident_type="Flood Emergency",
            location_name="MG Road, Bengaluru",
            severity="HIGH",
            needs=["rescue", "medical"],
            verification_status="PENDING",
            status="OPEN",
            citizen_id=citizen.id,
        )
        test_db.add(inc)
        test_db.commit()

        feedback_text = "Please specify the current water depth and if children or elderly are stranded."
        res = verify_incident(
            db=test_db,
            incident_id=inc.id,
            decision="NEED_MORE_INFORMATION",
            reason=feedback_text,
            admin_user=admin,
            mock_email_override=True,
        )

        assert res is not None
        assert res["verification_status"] == "NEEDS_MORE_INFO"
        assert res["admin_feedback"] == feedback_text
        assert res["email_sent"] is True
        assert res["email_status"] == "MOCKED"
        assert res["recipient_email_masked"] == "j******e@example.org"

        # Verify database record persistence
        refreshed_inc = test_db.get(Incident, inc.id)
        assert refreshed_inc.verification_status == "NEEDS_MORE_INFO"
        assert refreshed_inc.admin_feedback == feedback_text

        # Verify mock outbox details
        outbox = get_mock_outbox()
        assert len(outbox) == 1
        delivered = outbox[0]

        # 1. Recipient must be the authenticated citizen, NOT admin, NOT another citizen
        assert delivered["recipient"] == citizen.email
        assert delivered["recipient"] != admin.email
        assert delivered["recipient"] != sample_users["other"].email

        # 2. Subject must match requirement exactly
        assert delivered["subject"] == "Additional Information Required — ResQ-Sense Incident"

        # 3. Email body must include incident reference ID
        assert inc.id in delivered["text_body"]
        assert inc.id in delivered["html_body"]

        # 4. Email body must include category and location
        assert "Flood Emergency" in delivered["text_body"]
        assert "MG Road, Bengaluru" in delivered["text_body"]

        # 5. Email body must include admin's feedback
        assert feedback_text in delivered["text_body"]
        assert feedback_text in delivered["html_body"]

        # 6. Email body must contain clear instructions to sign in to ResQ-Sense Citizen Portal
        assert "Citizen Portal" in delivered["text_body"]
        assert "Track Status" in delivered["text_body"]
        assert citizen.email in delivered["text_body"]

    def test_needs_more_info_email_sent_via_linked_report_ownership(
        self, test_db: Session, sample_users: dict[str, User]
    ):
        """When incident.citizen_id is None, citizen is resolved via linked reports."""
        clear_mock_outbox()
        citizen = sample_users["citizen"]
        admin = sample_users["admin"]

        inc = Incident(
            id="INC-test-linked-02",
            incident_type="Building Fire",
            location_name="Sector 5, Salt Lake, Kolkata",
            severity="CRITICAL",
            needs=["fire_suppression"],
            verification_status="PENDING",
            citizen_id=None,  # Not directly on incident
        )
        test_db.add(inc)
        test_db.commit()

        rep = Report(
            id="REP-test-02",
            incident_id=inc.id,
            citizen_id=citizen.id,  # Linked on report
            original_text="Fire reported on 3rd floor",
            crisis_analysis={"incident_type": "Building Fire"},
            currentness_assessment={"currentness": "CURRENT"},
        )
        test_db.add(rep)
        test_db.commit()

        res = verify_incident(
            db=test_db,
            incident_id=inc.id,
            decision="NEED_MORE_INFORMATION",
            reason="Are stairwells clear for evacuation?",
            admin_user=admin,
            mock_email_override=True,
        )

        assert res["email_sent"] is True
        assert res["recipient_email_masked"] == "j******e@example.org"

        outbox = get_mock_outbox()
        assert len(outbox) == 1
        assert outbox[0]["recipient"] == citizen.email
        assert "Are stairwells clear for evacuation?" in outbox[0]["text_body"]

    def test_needs_more_info_missing_citizen_email(
        self, test_db: Session, sample_users: dict[str, User]
    ):
        """Anonymous incident without citizen email saves status & feedback and reports NO_RECIPIENT."""
        clear_mock_outbox()
        admin = sample_users["admin"]

        inc = Incident(
            id="INC-test-anon-03",
            incident_type="Gas Leak",
            location_name="Industrial Area Phase 2",
            severity="MEDIUM",
            verification_status="PENDING",
            citizen_id=None,
        )
        test_db.add(inc)
        test_db.commit()

        res = verify_incident(
            db=test_db,
            incident_id=inc.id,
            decision="NEED_MORE_INFORMATION",
            reason="Need exact pipeline building number.",
            admin_user=admin,
            mock_email_override=True,
        )

        assert res is not None
        assert res["verification_status"] == "NEEDS_MORE_INFO"
        assert res["admin_feedback"] == "Need exact pipeline building number."
        assert res["email_sent"] is False
        assert res["email_status"] == "NO_RECIPIENT"
        assert "No registered citizen email address" in res["email_error"]

        # Ensure database is updated
        refreshed = test_db.get(Incident, inc.id)
        assert refreshed.verification_status == "NEEDS_MORE_INFO"
        assert refreshed.admin_feedback == "Need exact pipeline building number."

        # Mock outbox remains empty
        assert len(get_mock_outbox()) == 0

    def test_needs_more_info_smtp_failure_preserves_database_state(
        self, test_db: Session, sample_users: dict[str, User]
    ):
        """When SMTP email service fails, status and feedback remain saved in DB (not rolled back)."""
        clear_mock_outbox()
        citizen = sample_users["citizen"]
        admin = sample_users["admin"]

        inc = Incident(
            id="INC-test-fail-04",
            incident_type="Landslide",
            location_name="Shimla Highway Km 42",
            severity="HIGH",
            verification_status="PENDING",
            citizen_id=citizen.id,
        )
        test_db.add(inc)
        test_db.commit()

        # Simulate SMTP server failure
        with unittest.mock.patch(
            "member4.verification_service.send_needs_more_info_email",
            return_value=EmailDeliveryResult(
                status="FAILED",
                recipient=citizen.email,
                subject="Additional Information Required — ResQ-Sense Incident",
                message="SMTP server connection refused",
                tracking_url="",
                error="SMTPServerDisconnected: Connection refused on port 587",
            ),
        ):
            res = verify_incident(
                db=test_db,
                incident_id=inc.id,
                decision="NEED_MORE_INFORMATION",
                reason="Is the road completely blocked or one lane passable?",
                admin_user=admin,
            )

        assert res is not None
        assert res["verification_status"] == "NEEDS_MORE_INFO"
        assert res["admin_feedback"] == "Is the road completely blocked or one lane passable?"
        assert res["email_sent"] is False
        assert res["email_status"] == "FAILED"
        assert "SMTPServerDisconnected" in res["email_error"]

        # CRITICAL: Verify database row still persisted the decision and feedback
        db_record = test_db.get(Incident, inc.id)
        assert db_record.verification_status == "NEEDS_MORE_INFO"
        assert db_record.admin_feedback == "Is the road completely blocked or one lane passable?"

    def test_other_decisions_do_not_trigger_email(
        self, test_db: Session, sample_users: dict[str, User]
    ):
        """Decisions like APPROVE or REJECT must NOT dispatch the Needs More Info notification."""
        clear_mock_outbox()
        citizen = sample_users["citizen"]
        admin = sample_users["admin"]

        inc = Incident(
            id="INC-test-other-05",
            incident_type="Structure Collapse",
            location_name="Old City Market",
            severity="HIGH",
            verification_status="PENDING",
            citizen_id=citizen.id,
        )
        test_db.add(inc)
        test_db.commit()

        # 1. APPROVE
        res_approve = verify_incident(
            db=test_db,
            incident_id=inc.id,
            decision="APPROVE",
            reason="Confirmed by police unit on site",
            admin_user=admin,
            mock_email_override=True,
        )
        assert res_approve["verification_status"] == "VERIFIED"
        assert res_approve["email_sent"] is None
        assert len(get_mock_outbox()) == 0

        # 2. REJECT
        res_reject = verify_incident(
            db=test_db,
            incident_id=inc.id,
            decision="REJECT",
            reason="Duplicate of existing incident",
            admin_user=admin,
            mock_email_override=True,
        )
        assert res_reject["verification_status"] == "REJECTED"
        assert res_reject["email_sent"] is None
        assert len(get_mock_outbox()) == 0

    def test_api_endpoint_verify_and_in_app_feedback_visibility(
        self, test_db: Session, sample_users: dict[str, User]
    ):
        """Integration test with FastAPI TestClient testing POST /incidents/{id}/verify and visibility in GET endpoints."""
        clear_mock_outbox()
        admin = sample_users["admin"]
        citizen = sample_users["citizen"]

        inc = Incident(
            id="INC-api-test-06",
            incident_type="Chemical Spill",
            location_name="Warehouse District B",
            severity="HIGH",
            needs=["hazmat"],
            verification_status="PENDING",
            status="OPEN",
            citizen_id=citizen.id,
        )
        test_db.add(inc)
        test_db.commit()

        app.dependency_overrides[get_db] = lambda: test_db
        try:
            client = TestClient(app)
            admin_token = create_access_token(
                user_id=admin.id,
                email=admin.email,
                role=admin.role,
            )
            citizen_token = create_access_token(
                user_id=citizen.id,
                email=citizen.email,
                role=citizen.role,
            )

            # 1. Authority submits Needs More Info
            verify_payload = {
                "decision": "NEED_MORE_INFORMATION",
                "reason": "Please state the chemical placard number (4-digit UN code).",
            }
            resp = client.post(
                f"/incidents/{inc.id}/verify",
                json=verify_payload,
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["incident_id"] == inc.id
            assert data["verification_status"] == "NEEDS_MORE_INFO"
            assert data["admin_feedback"] == verify_payload["reason"]
            assert data["email_sent"] is True
            assert data["recipient_email_masked"] == "j******e@example.org"

            # 2. Admin portal GET /incidents/{id} includes admin_feedback
            detail_resp = client.get(
                f"/incidents/{inc.id}",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            assert detail_resp.status_code == 200
            detail_data = detail_resp.json()
            assert detail_data["admin_feedback"] == verify_payload["reason"]

            # 3. Citizen portal GET /citizen/incidents includes admin_feedback
            citizen_list_resp = client.get(
                "/citizen/incidents",
                headers={"Authorization": f"Bearer {citizen_token}"},
            )
            assert citizen_list_resp.status_code == 200
            citizen_list = citizen_list_resp.json()
            matching = [i for i in citizen_list if i["incident_id"] == inc.id]
            assert len(matching) == 1
            assert matching[0]["admin_feedback"] == verify_payload["reason"]
            assert matching[0]["verification_status"] == "NEEDS_MORE_INFO"

            # 4. Authority GET /incidents list includes admin_feedback
            auth_list_resp = client.get(
                "/incidents",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            assert auth_list_resp.status_code == 200
            auth_list = auth_list_resp.json()
            matching_auth = [i for i in auth_list if i["incident_id"] == inc.id]
            assert len(matching_auth) == 1
            assert matching_auth[0]["admin_feedback"] == verify_payload["reason"]
        finally:
            app.dependency_overrides.pop(get_db, None)
