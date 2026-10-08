from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    JSON, Column, DateTime, Float, ForeignKey, String, Text
)
from sqlalchemy.orm import relationship

from .database import Base


def utc_now():
    return datetime.now(timezone.utc)


def new_incident_id():
    return f"INC-{uuid4().hex}"


def new_report_id():
    return f"REP-{uuid4().hex}"


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(String, primary_key=True, default=new_incident_id)

    incident_type = Column(String, nullable=False, index=True)
    location_name = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    severity = Column(String, nullable=False, default="UNKNOWN")
    needs = Column(JSON, nullable=False, default=list)

    # Human verification is separate from currentness assessment.
    verification_status = Column(
        String, nullable=False, default="PENDING"
    )
    status = Column(String, nullable=False, default="OPEN", index=True)
    response_status = Column(
    String,
    nullable=False,
    default="NOT_PLANNED",
    index=True,
)

    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(
        DateTime, nullable=False, default=utc_now, onupdate=utc_now
    )

    reports = relationship("Report", back_populates="incident")


class Report(Base):
    __tablename__ = "reports"

    id = Column(String, primary_key=True, default=new_report_id)

    # A report can remain unassigned until consolidation.
    incident_id = Column(
        String,
        ForeignKey("incidents.id"),
        nullable=True,
        index=True,
    )

    original_text = Column(Text, nullable=False)

    # Preserve the complete outputs, including evidence and locations.
    crisis_analysis = Column(JSON, nullable=False)
    currentness_assessment = Column(JSON, nullable=False)

    received_at = Column(DateTime, nullable=False, default=utc_now)

    incident = relationship("Incident", back_populates="reports")

class Resource(Base):
    __tablename__ = "resources"

    id = Column(
        String,
        primary_key=True,
        default=lambda: f"RES-{uuid4().hex}",
    )

    name = Column(String, nullable=False)

    # Examples: ambulance, fire_unit, rescue_team.
    resource_type = Column(String, nullable=False, index=True)

    # Examples: Medical Response, Fire Response.
    department = Column(String, nullable=False)

    # Needs this resource can support, such as medical or rescue.
    capabilities = Column(JSON, nullable=False, default=list)

    location_name = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    # AVAILABLE, BUSY, or OFFLINE.
    availability = Column(
        String,
        nullable=False,
        default="AVAILABLE",
        index=True,
    )

    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )