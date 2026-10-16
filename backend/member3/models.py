from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
)
from sqlalchemy.orm import relationship

from .database import Base


def utc_now():
    return datetime.now(timezone.utc)


def new_incident_id():
    return f"INC-{uuid4().hex}"


def new_report_id():
    return f"REP-{uuid4().hex}"


def new_user_id():
    return f"USER-{uuid4().hex}"


def new_verification_id():
    return f"VERIF-{uuid4().hex}"


class AccountVerification(Base):
    __tablename__ = "account_verifications"

    id = Column(String, primary_key=True, default=new_verification_id)
    email = Column(String, unique=True, index=True, nullable=False)
    code_hash = Column(String, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    attempts_count = Column(Integer, default=0, nullable=False)
    resend_count = Column(Integer, default=0, nullable=False)
    last_sent_at = Column(DateTime, default=utc_now, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=new_user_id)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="citizen", index=True)

    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(
        DateTime, nullable=False, default=utc_now, onupdate=utc_now
    )

    incidents = relationship("Incident", back_populates="citizen")
    reports = relationship("Report", back_populates="citizen")


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

    # Optional citizen ownership association (nullable for legacy/authority incidents)
    citizen_id = Column(
        String,
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    # Admin / commander feedback or notes (e.g. for NEEDS_MORE_INFO, APPROVE, REJECT)
    admin_feedback = Column(Text, nullable=True)

    citizen = relationship("User", back_populates="incidents")
    reports = relationship(
        "Report",
        back_populates="incident",
        cascade="all, delete-orphan",
    )


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

    # Optional citizen ownership association
    citizen_id = Column(
        String,
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    original_text = Column(Text, nullable=False)

    # Preserve the complete outputs, including evidence and locations.
    crisis_analysis = Column(JSON, nullable=False)
    currentness_assessment = Column(JSON, nullable=False)

    received_at = Column(DateTime, nullable=False, default=utc_now)

    citizen = relationship("User", back_populates="reports")
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


# Automatically apply safe, backward-compatible schema updates
from .database import engine, ensure_schema_compatibility

try:
    ensure_schema_compatibility(engine)
except Exception:
    pass