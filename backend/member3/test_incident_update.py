from .models import Incident, Report
from .incident_service import update_incident_details


if __name__ == "__main__":
    incident = Incident(
        incident_type="Fire",
        severity="HIGH",
        needs=["rescue"],
    )

    report = Report(
        original_text="Sample report for testing",
        crisis_analysis={
            "severity": "CRITICAL",
            "needs": ["medical"],
        },
        currentness_assessment={},
    )

    update_incident_details(incident, report)

    assert incident.needs == ["medical", "rescue"]
    assert incident.severity == "CRITICAL"
    assert incident.updated_at is not None

    # A lower severity must not reduce the incident's severity.
    report.crisis_analysis = {
        "severity": "LOW",
        "needs": ["rescue"],
    }

    update_incident_details(incident, report)

    assert incident.severity == "CRITICAL"
    assert incident.needs == ["medical", "rescue"]

    print("Incident update checks passed")