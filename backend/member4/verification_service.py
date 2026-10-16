from __future__ import annotations

import logging
from typing import Optional
from sqlalchemy.orm import Session

from member3.models import Incident, User, Report, utc_now
from email_service import send_needs_more_info_email

logger = logging.getLogger("resqsense.verification")


def _mask_email(email: str) -> str:
    """Mask email for privacy in audit logs and API responses (e.g., j***n@example.com)."""
    if not email or "@" not in email:
        return email
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"


def verify_incident(
    db: Session,
    incident_id: str,
    decision: str,
    reason: str | None = None,
    admin_user: User | None = None,
    mock_email_override: bool | None = None,
):
    """
    Apply a human verification decision to an incident.

    AI recommends.
    Human administrator makes the final decision.
    When 'NEED_MORE_INFORMATION' is selected, administrator feedback is saved,
    and a notification email is dispatched to the citizen who reported the incident.
    """

    incident = (
        db.query(Incident)
        .filter(Incident.id == incident_id)
        .first()
    )

    if incident is None:
        return None

    clean_reason = reason.strip() if (reason and reason.strip()) else None

    email_sent: Optional[bool] = None
    email_status: Optional[str] = None
    email_error: Optional[str] = None
    recipient_email_masked: Optional[str] = None

    if decision == "APPROVE":
        incident.verification_status = "VERIFIED"
        if clean_reason:
            incident.admin_feedback = clean_reason
        incident.updated_at = utc_now()
        db.commit()
        db.refresh(incident)

        return_message = "Incident approved by human administrator."

    elif decision == "REJECT":
        incident.verification_status = "REJECTED"
        if clean_reason:
            incident.admin_feedback = clean_reason
        incident.updated_at = utc_now()
        db.commit()
        db.refresh(incident)

        return_message = "Incident rejected by human administrator."

    elif decision == "NEED_MORE_INFORMATION":
        incident.verification_status = "NEEDS_MORE_INFO"
        feedback_text = (
            clean_reason
            if clean_reason
            else "Additional information and situation updates requested by emergency response authorities."
        )
        incident.admin_feedback = feedback_text
        incident.updated_at = utc_now()

        # Step 1: Save verification status and feedback first to preserve state
        # even if downstream notification or SMTP fails.
        db.commit()
        db.refresh(incident)

        # Step 2: Retrieve the email address of the citizen who submitted the incident
        # via authenticated incident ownership / linked reports.
        citizen: Optional[User] = None
        if incident.citizen_id:
            citizen = db.get(User, incident.citizen_id)

        if not citizen:
            # Fallback to linked reports submitted by an authenticated citizen
            reports = (
                db.query(Report)
                .filter(Report.incident_id == incident.id)
                .order_by(Report.received_at.asc())
                .all()
            )
            for rep in reports:
                if rep.citizen_id:
                    c = db.get(User, rep.citizen_id)
                    if c:
                        citizen = c
                        break

        # Step 3: Dispatch email notification if recipient citizen email is resolved
        if not citizen or not citizen.email:
            email_sent = False
            email_status = "NO_RECIPIENT"
            email_error = "No registered citizen email address associated with this incident."
            recipient_email_masked = None
            return_message = (
                "Additional information requested. Status saved (no citizen email associated with report)."
            )
            logger.info(
                "Needs more info requested for incident %s, but no registered citizen email found.",
                incident.id,
            )
        else:
            recipient_email = citizen.email
            citizen_name = citizen.full_name or "Citizen Reporter"
            recipient_email_masked = _mask_email(recipient_email)
            admin_name = (
                admin_user.full_name
                if (admin_user and admin_user.full_name)
                else "Emergency Operations Authority"
            )

            try:
                delivery_res = send_needs_more_info_email(
                    recipient_email=recipient_email,
                    citizen_name=citizen_name,
                    incident_id=incident.id,
                    feedback=feedback_text,
                    incident_type=incident.incident_type,
                    location_name=incident.location_name,
                    admin_name=admin_name,
                    mock_mode_override=mock_email_override,
                )
                email_sent = delivery_res.success
                email_status = delivery_res.status
                email_error = delivery_res.error

                if delivery_res.success:
                    return_message = (
                        f"Additional information requested. Notification email dispatched to {recipient_email_masked}."
                    )
                else:
                    return_message = (
                        f"Verification status updated to Needs More Info, but email delivery failed ({delivery_res.error or 'Delivery failed'})."
                    )
            except Exception as exc:
                logger.exception(
                    "Unexpected exception while sending needs-more-info email for incident %s",
                    incident.id,
                )
                email_sent = False
                email_status = "FAILED"
                email_error = f"{type(exc).__name__}: {str(exc)}"
                return_message = (
                    f"Verification status updated to Needs More Info, but email service encountered an error ({type(exc).__name__})."
                )

    else:
        raise ValueError("Invalid verification decision.")

    return {
        "incident_id": incident.id,
        "decision": decision,
        "verification_status": incident.verification_status,
        "reason": clean_reason,
        "admin_feedback": incident.admin_feedback,
        "message": return_message,
        "email_sent": email_sent,
        "email_status": email_status,
        "email_error": email_error,
        "recipient_email_masked": recipient_email_masked,
    }