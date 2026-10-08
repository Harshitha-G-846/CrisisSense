from sqlalchemy.orm import Session

from member3.models import Incident


def verify_incident(
    db: Session,
    incident_id: str,
    decision: str,
    reason: str | None = None
):
    """
    Apply a human verification decision to an incident.

    AI recommends.
    Human administrator makes the final decision.
    """

    incident = (
        db.query(Incident)
        .filter(Incident.id == incident_id)
        .first()
    )

    if incident is None:
        return None

    if decision == "APPROVE":
        incident.verification_status = "VERIFIED"

        return_message = (
            "Incident approved by human administrator."
        )

    elif decision == "REJECT":
        incident.verification_status = "REJECTED"

        return_message = (
            "Incident rejected by human administrator."
        )

    elif decision == "NEED_MORE_INFORMATION":
        incident.verification_status = "NEEDS_MORE_INFO"

        return_message = (
            "Additional information requested from the reporter."
        )

    else:
        raise ValueError("Invalid verification decision.")

    db.commit()
    db.refresh(incident)

    return {
        "incident_id": incident.id,
        "decision": decision,
        "verification_status": incident.verification_status,
        "reason": reason,
        "message": return_message,
    }