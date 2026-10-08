from datetime import datetime, timezone

from sqlalchemy.orm import Session

from member3.models import Incident


def authorize_response(
    db: Session,
    incident_id: str,
):
    """
    Authorize a previously generated response plan.

    AI / resource matching recommends a response.
    A human administrator explicitly authorizes it.

    No resource is automatically dispatched here.
    """

    incident = (
        db.query(Incident)
        .filter(Incident.id == incident_id)
        .first()
    )

    if incident is None:
        return None

    # Response authorization is allowed only after
    # the incident has been human-verified.
    if incident.verification_status != "VERIFIED":
        return {
            "success": False,
            "incident_id": incident.id,
            "response_status": incident.response_status,
            "message": (
                "Response cannot be authorized because "
                "the incident has not been human verified."
            ),
        }

    # Prevent duplicate authorization.
    if incident.response_status == "AUTHORIZED":
        return {
            "success": True,
            "incident_id": incident.id,
            "response_status": incident.response_status,
            "message": "Response is already authorized.",
        }

    # A response should be planned before authorization.
    if incident.response_status != "PLANNED":
        return {
            "success": False,
            "incident_id": incident.id,
            "response_status": incident.response_status,
            "message": (
                "Response cannot be authorized before "
                "a response plan has been generated."
            ),
        }

    incident.response_status = "AUTHORIZED"
    incident.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(incident)

    return {
        "success": True,
        "incident_id": incident.id,
        "response_status": incident.response_status,
        "verification_status": incident.verification_status,
        "incident_status": incident.status,
        "message": (
            "Response plan authorized by human administrator. "
            "No automatic resource dispatch was performed."
        ),
    }