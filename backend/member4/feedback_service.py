from datetime import datetime, timezone

from sqlalchemy.orm import Session

from member3.models import Incident


def process_feedback(
    db: Session,
    incident_id: str,
    feedback: str,
):
    """
    Process new citizen feedback for an existing incident.

    Member 4:
    - receives human/citizen feedback
    - detects whether the situation has changed
    - identifies additional needs
    - updates the incident
    - signals that replanning may be required
    """

    incident = (
        db.query(Incident)
        .filter(Incident.id == incident_id)
        .first()
    )

    if incident is None:
        return None

    feedback_lower = feedback.lower()

    # Detect indications that the situation is getting worse
    escalation_keywords = [
        "spreading",
        "worsening",
        "getting worse",
        "escalating",
        "increasing",
        "more people",
        "trapped",
        "larger",
        "expanded",
        "out of control",
    ]

    # Detect additional resource/assistance needs
    additional_need_keywords = {
        "water": "water",
        "tanker": "water",
        "tankers": "water",
        "ambulance": "medical",
        "doctor": "medical",
        "medical": "medical",
        "rescue": "rescue",
        "food": "food",
        "shelter": "shelter",
    }

    situation_changed = any(
        keyword in feedback_lower
        for keyword in escalation_keywords
    )

    detected_needs = []

    for keyword, need in additional_need_keywords.items():
        if keyword in feedback_lower and need not in detected_needs:
            detected_needs.append(need)

    # Preserve existing needs
    current_needs = list(incident.needs or [])

    # Add newly detected needs
    for need in detected_needs:
        if need not in current_needs:
            current_needs.append(need)

    # Only move to IN_PROGRESS when the incident is already verified.
    # This preserves the human-verification workflow.
    if (
        situation_changed
        and incident.verification_status == "VERIFIED"
    ):
        incident.status = "IN_PROGRESS"

    incident.needs = current_needs
    incident.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(incident)

    return {
        "incident_id": incident.id,
        "feedback": feedback,
        "situation_changed": situation_changed,
        "detected_needs": detected_needs,
        "updated_needs": current_needs,
        "status": incident.status,
        "message": (
            "Situation changed. Replanning is required."
            if situation_changed
            else "Feedback recorded. No major situation change detected."
        ),
    }