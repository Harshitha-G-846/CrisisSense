from sqlalchemy.orm import Session
from .models import Incident, Report
from datetime import timedelta
from sqlalchemy import select
from .models import utc_now
from .location_matching import location_matches
from .similarity import text_similarity

def normalize_text(text: str) -> str:
    return " ".join(text.casefold().split())


def find_duplicate_incident(
    db: Session,
    report: Report,
) -> Incident | None:
    analysis = report.crisis_analysis
    incident_type = analysis.get("incident_type")

    if not incident_type or incident_type.casefold() == "unknown":
        return None

    locations = analysis.get("locations") or []
    location = locations[0] if locations else {}

    cutoff = report.received_at - timedelta(hours=24)

    statement = (
        select(Report, Incident)
        .join(Incident, Report.incident_id == Incident.id)
        .where(
            Report.id != report.id,
            Report.received_at >= cutoff,
            Report.received_at <= report.received_at,
            Incident.incident_type == incident_type,
            Incident.status.in_(["OPEN", "IN_PROGRESS"]),
            Incident.verification_status != "REJECTED",
        )
        .order_by(Report.received_at.desc())
    )

    exact_matches = {}
    similar_matches = {}
    similarity_threshold = 0.80

    for previous_report, incident in db.execute(statement):
        # Both exact and semantic matches must pass location checking.
        if not location_matches(incident, location):
            continue

        if normalize_text(previous_report.original_text) == normalize_text(
            report.original_text
        ):
            exact_matches[incident.id] = incident
            continue

        score = text_similarity(
            previous_report.original_text,
            report.original_text,
        )

        if score >= similarity_threshold:
            similar_matches[incident.id] = incident

    # Prefer a unique exact match.
    if len(exact_matches) == 1:
        return next(iter(exact_matches.values()))

    if len(exact_matches) > 1:
        return None

    # Several reports from one incident still count as one candidate.
    if len(similar_matches) == 1:
        return next(iter(similar_matches.values()))

    # No match or multiple possible incidents: do not pick arbitrarily.
    return None

def update_incident_details(
    incident: Incident,
    report: Report,
) -> None:
    analysis = report.crisis_analysis

    # Assign a new list so SQLAlchemy detects the JSON change.
    incident.needs = sorted(
        set(incident.needs or [])
        | set(analysis.get("needs") or [])
    )

    severity_rank = {
        "UNKNOWN": 0,
        "LOW": 1,
        "MEDIUM": 2,
        "HIGH": 3,
        "CRITICAL": 4,
    }

    incoming_severity = str(
        analysis.get("severity") or "UNKNOWN"
    ).upper()

    current_severity = str(
        incident.severity or "UNKNOWN"
    ).upper()

    if severity_rank.get(incoming_severity, 0) > severity_rank.get(
        current_severity, 0
    ):
        incident.severity = incoming_severity

    incident.updated_at = utc_now()


def create_incident_from_report(
    db: Session,
    report: Report,
) -> Incident | None:
    # If already linked, return the existing incident.
    if report.incident_id:
        return db.get(Incident, report.incident_id)

    analysis = report.crisis_analysis

    # Keep non-crisis or unclassified reports without an incident.
    if analysis.get("is_crisis") is not True:
        return None

    # Keep reports assessed as old for review rather than
    # creating an active incident automatically.
    assessment = report.currentness_assessment
    if assessment.get("currentness") == "OLD":
        return None
    existing_incident = find_duplicate_incident(db, report)

    if existing_incident is not None:
        try:
            report.incident_id = existing_incident.id
            update_incident_details(existing_incident, report)
            db.commit()
            db.refresh(existing_incident)
        except Exception:
            db.rollback()
            raise

        return existing_incident

    locations = analysis.get("locations") or []
    location = locations[0] if locations else {}

    incident = Incident(
        incident_type=analysis.get("incident_type") or "Unknown",
        location_name=location.get("text"),
        latitude=location.get("latitude"),
        longitude=location.get("longitude"),
        severity=analysis.get("severity") or "UNKNOWN",
        needs=list(analysis.get("needs") or []),
        verification_status="PENDING",
        status="OPEN",
    )

    try:
        db.add(incident)

        # Insert the incident and generate its ID,
        # without committing the transaction yet.
        db.flush()

        # Link the saved report to that incident.
        report.incident_id = incident.id

        # Save the incident and link together.
        db.commit()
        db.refresh(incident)
    except Exception:
        db.rollback()
        raise

    return incident