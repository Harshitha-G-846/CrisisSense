from sqlalchemy.orm import Session

from member3.models import Incident
from member3.resource_service import recommend_resources


def generate_revised_plan(
    db: Session,
    incident_id: str,
):
    """
    Generate a revised response recommendation after
    the incident situation has changed.

    Member 4 orchestrates the workflow.
    Member 3 performs the actual resource matching.
    """

    incident = (
        db.query(Incident)
        .filter(Incident.id == incident_id)
        .first()
    )

    if incident is None:
        return None

    recommendations = recommend_resources(
        db=db,
        incident=incident,
    )

    incident.response_status = "PLANNED"

    db.commit()
    db.refresh(incident)

    return {
        "incident_id": incident.id,
        "incident_type": incident.incident_type,
        "location": incident.location_name,
        "severity": incident.severity,
        "needs": incident.needs,
        "resource_recommendation": recommendations,
        "human_approval_required": True,
        "message": (
            "Revised response plan generated. "
            "Human administrator approval is required."
        ),
    }