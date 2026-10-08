"""
main.py — CrisisSense FastAPI backend
Member 1 (crisis analysis) + Member 2 (multimodal currentness verification)

/analyze accepts both:
  - JSON body  (text-only, backwards compatible)
  - multipart/form-data  (text + optional image/video/audio)
"""
from __future__ import annotations


from fastapi import Depends
from sqlalchemy.orm import Session

from member3.database import get_db
from member3.report_service import save_report
from member3.incident_service import create_incident_from_report
from sqlalchemy import select, func
from member3.models import Incident, Report
from typing import Literal
from fastapi import Query
from member3.models import Resource
from member3.resource_service import recommend_resources
from datetime import timezone
from member3.models import utc_now

import os
import tempfile
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from member1.pipeline import analyze_crisis
from member2.currentness_agent import run_currentness_verification
from member2.schemas import Member1Context

from member4.authorization_service import authorize_response
from member4.schemas import VerificationRequest, FeedbackRequest
from member4.feedback_service import process_feedback
from member4.replanning_service import generate_revised_plan
from member4.verification_service import verify_incident
# ---------------------------------------------------------------------------
# Allowed media extensions
# ---------------------------------------------------------------------------
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tiff"}
_VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv", ".mpeg"}
_AUDIO_EXTS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".opus", ".webm"}


app = FastAPI(
    title="CrisisSense API",
    description=(
        "CrisisSense multimodal crisis intelligence API. "
        "POST /analyze accepts text (JSON or form) plus optional image, video, and audio uploads."
    ),
    version="2.0",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ext(filename: Optional[str]) -> str:
    if not filename:
        return ""
    return os.path.splitext(filename)[-1].lower()


def _validate_ext(filename: Optional[str], allowed: set, label: str) -> None:
    """Raise HTTP 415 if the uploaded file extension is not in the allowed set."""
    ext = _ext(filename)
    if ext not in allowed:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Unsupported {label} file type '{ext}'. "
                f"Allowed: {sorted(allowed)}"
            ),
        )


def _save_upload(upload: UploadFile, suffix: str) -> str:
    """Write UploadFile content to a named temp file and return its path."""
    with tempfile.NamedTemporaryFile(
        suffix=suffix, delete=False, prefix="crisisense_"
    ) as tf:
        tf.write(upload.file.read())
        return tf.name


def _build_member1_context(m1: dict) -> Member1Context:
    """Convert the analyze_crisis dict into a Member1Context for Member 2."""
    return Member1Context(
        is_crisis=m1.get("is_crisis"),
        incident_type=m1.get("incident_type"),
        information_type=m1.get("information_type"),
        severity=m1.get("severity"),
        needs=m1.get("needs") or [],
        locations=m1.get("locations") or [],
    )


def _format_currentness(result) -> dict:
    """Serialise CurrentnessResult to a plain dict for the JSON response."""
    return {
        "currentness": result.currentness.value,
        "confidence": result.confidence,
        "action": result.action.value,
        "conflicts_detected": result.conflicts_detected,
        "evidence": [
            {
                "source": ev.source.value,
                "polarity": ev.polarity.value,
                "weight": ev.weight,
                "finding": ev.finding,
                "details": ev.details,
            }
            for ev in result.evidence
        ],
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------



@app.get("/")
def home():
    return {"message": "CrisisSense API is running", "version": "2.0"}


# ── JSON text-only endpoint (backwards compatible) ───────────────────────────

class CrisisRequest(BaseModel):
    text: str

@app.post("/incidents/{incident_id}/feedback")
def submit_feedback(
    incident_id: str,
    request: FeedbackRequest,
    db: Session = Depends(get_db),
):
    result = process_feedback(
        db=db,
        incident_id=incident_id,
        feedback=request.feedback,
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Incident not found"
        )

    return result


@app.post("/incidents/{incident_id}/authorize")
def authorize_incident_response(
    incident_id: str,
    db: Session = Depends(get_db),
):
    result = authorize_response(
        db=db,
        incident_id=incident_id,
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Incident not found",
        )

    if result.get("success") is False:
        raise HTTPException(
            status_code=400,
            detail=result["message"],
        )

    return result

@app.post("/incidents/{incident_id}/replan")
def replan_incident(
    incident_id: str,
    db: Session = Depends(get_db),
):
    result = generate_revised_plan(
        db=db,
        incident_id=incident_id,
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Incident not found"
        )

    return result

@app.post("/analyze-text")
def analyze_text(
    request: CrisisRequest,
    db: Session = Depends(get_db),
):
    if not request.text.strip():
        raise HTTPException(
            status_code=422,
            detail="Report text cannot be empty.",
        )

    # Member 1: identify crisis details.
    m1_result = analyze_crisis(request.text)
    m1_context = _build_member1_context(m1_result)

    # Member 2: assess currentness and collect evidence.
    currentness_result = run_currentness_verification(
        text=request.text,
        member1_context=m1_context,
    )
    currentness_data = _format_currentness(currentness_result)

    # Member 3: preserve the original text and both outputs.
    report = save_report(
        db=db,
        original_text=request.text,
        crisis_analysis=m1_result,
        currentness_assessment=currentness_data,
    )

    create_incident_from_report(db=db, report=report)

    return {
        "report_id": report.id,
        "incident_id": report.incident_id,
        "crisis_analysis": m1_result,
        "currentness": currentness_data,
    }


# ── Multipart form-data endpoint (text + optional media uploads) ─────────────

@app.post("/analyze")
async def analyze(
    text: Optional[str] = Form(default=None),
    image: Optional[UploadFile] = File(default=None),
    video: Optional[UploadFile] = File(default=None),
    audio: Optional[UploadFile] = File(default=None),
    db: Session = Depends(get_db),
):
    """
    Multimodal /analyze endpoint.

    Accepts multipart/form-data with:
      - text    (form field, optional)
      - image   (file upload, optional)
      - video   (file upload, optional)
      - audio   (file upload, optional)

    All media is written to a temporary directory, analysed, then deleted.
    At least one modality (text, image, video, or audio) must be provided.
    """
    # Guard: at least one modality required
    has_text = text and text.strip()
    has_image = image and image.filename
    has_video = video and video.filename
    has_audio = audio and audio.filename

    if not any([has_text, has_image, has_video, has_audio]):
        raise HTTPException(
            status_code=422,
            detail="At least one modality is required: text, image, video, or audio.",
        )

    # Validate file extensions before saving anything
    if has_image:
        _validate_ext(image.filename, _IMAGE_EXTS, "image")
    if has_video:
        _validate_ext(video.filename, _VIDEO_EXTS, "video")
    if has_audio:
        _validate_ext(audio.filename, _AUDIO_EXTS, "audio")

    # Save uploads to temp files
    temp_paths: list[str] = []
    image_path: Optional[str] = None
    video_path: Optional[str] = None
    audio_path: Optional[str] = None

    try:
        if has_image:
            image_path = _save_upload(image, suffix=_ext(image.filename))
            temp_paths.append(image_path)

        if has_video:
            video_path = _save_upload(video, suffix=_ext(video.filename))
            temp_paths.append(video_path)

        if has_audio:
            audio_path = _save_upload(audio, suffix=_ext(audio.filename))
            temp_paths.append(audio_path)

        # Member 1: text-based crisis analysis.
        # Guard: analyze_crisis requires non-empty text (Member 1's zero-shot
        # severity model raises ValueError on empty sequences).
        if text and text.strip():
            m1_result = analyze_crisis(text.strip())
        else:
            # No text supplied — Member 1 cannot classify without text.
            m1_result = {
                "is_crisis": None,
                "incident_type": None,
                "information_type": None,
                "severity": None,
                "needs": [],
                "locations": [],
            }
        m1_context = _build_member1_context(m1_result)

        # Member 2: multimodal currentness verification
        currentness_result = run_currentness_verification(
            text=text or None,
            image_path=image_path,
            video_path=video_path,
            audio_path=audio_path,
            member1_context=m1_context,
        )

    finally:
        # Always clean up temporary files
        for path in temp_paths:
            try:
                if path and os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass

    currentness_data = _format_currentness(currentness_result)

    report_id = None
    incident_id = None
    storage_status = "NOT_SAVED_MEDIA_ONLY"

    if text and text.strip():
        report = save_report(
            db=db,
            original_text=text.strip(),
            crisis_analysis=m1_result,
            currentness_assessment=currentness_data,
        )

        create_incident_from_report(db=db, report=report)

        report_id = report.id
        incident_id = report.incident_id
        storage_status = "SAVED"

    return {
        "report_id": report_id,
        "incident_id": incident_id,
        "storage_status": storage_status,
        "crisis_analysis": m1_result,
        "currentness": currentness_data,
    }

@app.get("/incidents")
def list_incidents(db: Session = Depends(get_db)):
    statement = (
        select(
            Incident,
            func.count(Report.id).label("report_count"),
        )
        .outerjoin(Report, Report.incident_id == Incident.id)
        .group_by(Incident.id)
        .order_by(Incident.created_at.desc())
    )

    rows = db.execute(statement).all()

    return [
        {
            "incident_id": incident.id,
            "incident_type": incident.incident_type,
            "location_name": incident.location_name,
            "latitude": incident.latitude,
            "longitude": incident.longitude,
            "severity": incident.severity,
            "needs": incident.needs,
            "status": incident.status,
            "verification_status": incident.verification_status,
            "report_count": report_count,
            "created_at": utc_timestamp(incident.created_at),
            "updated_at": utc_timestamp(incident.updated_at),
        }
        for incident, report_count in rows
    ]

@app.post("/incidents/{incident_id}/verify")
def verify_incident_endpoint(
    incident_id: str,
    request: VerificationRequest,
    db: Session = Depends(get_db),
):
    result = verify_incident(
        db=db,
        incident_id=incident_id,
        decision=request.decision,
        reason=request.reason,
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Incident not found"
        )

    return result


@app.get("/resources")
def list_resources(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    resource_type: Optional[str] = None,
    availability: Optional[
        Literal["AVAILABLE", "BUSY", "OFFLINE"]
    ] = None,
    db: Session = Depends(get_db),
):
    filters = []

    if resource_type:
        filters.append(Resource.resource_type == resource_type)

    if availability:
        filters.append(Resource.availability == availability)

    total = db.scalar(
        select(func.count())
        .select_from(Resource)
        .where(*filters)
    )

    resources = db.scalars(
        select(Resource)
        .where(*filters)
        .order_by(Resource.id)
        .offset(offset)
        .limit(limit)
    ).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "resource_id": resource.id,
                "name": resource.name,
                "resource_type": resource.resource_type,
                "department": resource.department,
                "capabilities": resource.capabilities,
                "location_name": resource.location_name,
                "latitude": resource.latitude,
                "longitude": resource.longitude,
                "availability": resource.availability,
            }
            for resource in resources
        ],
    }

@app.get("/incidents/{incident_id}/resources")
def incident_resources(
    incident_id: str,
    radius_km: float = Query(default=25.0, gt=0, le=100),
    per_need: int = Query(default=3, ge=1, le=10),
    db: Session = Depends(get_db),
):
    incident = db.get(Incident, incident_id)

    if incident is None:
        raise HTTPException(
            status_code=404,
            detail="Incident not found.",
        )

    return recommend_resources(
        db=db,
        incident=incident,
        radius_km=radius_km,
        per_need=per_need,
    )


def utc_timestamp(value):
    if value is None:
        return None

    # Our SQLite timestamps were written using UTC.
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc).isoformat()


@app.get("/incidents/{incident_id}")
def incident_details(
    incident_id: str,
    db: Session = Depends(get_db),
):
    incident = db.get(Incident, incident_id)

    if incident is None:
        raise HTTPException(
            status_code=404,
            detail="Incident not found.",
        )

    reports = db.scalars(
        select(Report)
        .where(Report.incident_id == incident_id)
        .order_by(Report.received_at, Report.id)
    ).all()

    return {
        "incident_id": incident.id,
        "incident_type": incident.incident_type,
        "location_name": incident.location_name,
        "latitude": incident.latitude,
        "longitude": incident.longitude,
        "severity": incident.severity,
        "needs": incident.needs,
        "status": incident.status,
        "verification_status": incident.verification_status,
        "created_at": utc_timestamp(incident.created_at),
        "updated_at": utc_timestamp(incident.updated_at),
        "report_count": len(reports),
        "reports": [
            {
                "report_id": report.id,
                "original_text": report.original_text,
                "crisis_analysis": report.crisis_analysis,
                "currentness": report.currentness_assessment,
                "received_at": utc_timestamp(report.received_at),
            }
            for report in reports
        ],
    }

class IncidentStatusUpdate(BaseModel):
    status: Literal["OPEN", "IN_PROGRESS", "RESOLVED"]


@app.patch("/incidents/{incident_id}/status")
def update_incident_status(
    incident_id: str,
    request: IncidentStatusUpdate,
    db: Session = Depends(get_db),
):
    incident = db.get(Incident, incident_id)

    if incident is None:
        raise HTTPException(
            status_code=404,
            detail="Incident not found.",
        )

    if (
        request.status == "IN_PROGRESS"
        and incident.verification_status != "VERIFIED"
    ):
        raise HTTPException(
            status_code=409,
            detail="Human verification is required before response begins.",
        )

    if incident.status != request.status:
        try:
            incident.status = request.status
            incident.updated_at = utc_now()
            db.commit()
            db.refresh(incident)
        except Exception:
            db.rollback()
            raise

    return {
        "incident_id": incident.id,
        "status": incident.status,
        "verification_status": incident.verification_status,
        "updated_at": utc_timestamp(incident.updated_at),
    }