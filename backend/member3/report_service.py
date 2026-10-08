from sqlalchemy.orm import Session

from .models import Report


def save_report(
    db: Session,
    original_text: str,
    crisis_analysis: dict,
    currentness_assessment: dict,
) -> Report:
    if not original_text.strip():
        raise ValueError("Report text cannot be empty.")

    report = Report(
        original_text=original_text,
        crisis_analysis=crisis_analysis,
        currentness_assessment=currentness_assessment,
    )

    try:
        db.add(report)
        db.commit()
        db.refresh(report)
    except Exception:
        db.rollback()
        raise

    return report