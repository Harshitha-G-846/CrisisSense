
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .database import Base
from .models import Incident, Report
from .incident_service import create_incident_from_report


def test_prefers_city_over_state():
    # An isolated in-memory database; the real DB is untouched.
    engine = create_engine("sqlite:///:memory:")
    TestSession = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )
    Base.metadata.create_all(engine)

    try:
        with TestSession() as db:
            report = Report(
                original_text="Flooding reported in Guwahati, Assam.",
                crisis_analysis={
                    "is_crisis": True,
                    "incident_type": "Flood",
                    "severity": "HIGH",
                    "needs": ["rescue"],
                    "locations": [
                        {
                            "text": "Assam",
                            "location_type": "state",
                            "latitude": 26.4073841,
                            "longitude": 93.2551303,
                        },
                        {
                            "text": "Guwahati",
                            "location_type": "city",
                            "latitude": 26.1805978,
                            "longitude": 91.753943,
                        },
                    ],
                },
                currentness_assessment={"currentness": "CURRENT"},
            )
            db.add(report)
            db.commit()

            incident = create_incident_from_report(db, report)

            assert incident is not None
            assert incident.location_name == "Guwahati", (
                f"Expected Guwahati, got {incident.location_name!r}"
            )
            assert incident.latitude == 26.1805978
            assert incident.longitude == 91.753943

            print("Incident location priority check passed")

    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


if __name__ == "__main__":
    test_prefers_city_over_state()
