from .database import SessionLocal
from .models import Report
from .report_service import save_report


if __name__ == "__main__":
    with SessionLocal() as db:
        report = save_report(
            db=db,
            original_text="TEST: Fire in Whitefield; people need rescue.",
            crisis_analysis={
                "is_crisis": True,
                "incident_type": "Fire",
                "severity": "HIGH",
                "needs": ["rescue"],
                "locations": [{"text": "Whitefield"}],
            },
            currentness_assessment={
                "currentness": "UNCERTAIN",
                "confidence": 0.0,
                "action": "HUMAN_VERIFICATION_REQUIRED",
                "evidence": [],
                "conflicts_detected": [],
            },
        )
        report_id = report.id

    # Use a new session to confirm the report was saved permanently.
    with SessionLocal() as db:
        stored_report = db.get(Report, report_id)

        if stored_report is None:
            raise RuntimeError("Report was not found in the database.")

        print("Report saved and read back successfully")
        print("Report ID:", stored_report.id)
        print("Text:", stored_report.original_text)
        print("Incident ID:", stored_report.incident_id)