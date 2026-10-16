"""
main.py — CrisisSense FastAPI backend
Member 1 (crisis analysis) + Member 2 (multimodal currentness verification)

/analyze accepts both:
  - JSON body  (text-only, backwards compatible)
  - multipart/form-data  (text + optional image/video/audio)
"""
from __future__ import annotations


from dotenv import load_dotenv
load_dotenv()

from fastapi import Depends
from sqlalchemy.orm import Session

from member3.database import get_db
from member3.report_service import save_report
from member3.incident_service import create_incident_from_report, delete_incident
from sqlalchemy import select, func
from member3.models import Incident, Report, Resource, User, AccountVerification
from typing import Literal
from fastapi import Query
from member3.resource_service import recommend_resources
from datetime import timedelta, timezone
from member3.models import utc_now

from auth import (
    hash_password,
    verify_password,
    validate_email_address,
    validate_password_strength,
    create_access_token,
    get_current_user,
    get_current_user_optional,
    get_current_authority_user,
    get_current_citizen_user,
    require_authority,
    generate_verification_code,
    hash_verification_code,
    verify_code_hash,
)
from email_service import (
    send_incident_confirmation_email,
    send_verification_code_email,
    send_admin_information_request_email,
    send_needs_more_info_email,
)

import os
import tempfile
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from member1.pipeline import analyze_crisis
import member1.pipeline as _m1_pipe
if hasattr(_m1_pipe, "crisis_model") and not hasattr(_m1_pipe.crisis_model, "multi_class"):
    _m1_pipe.crisis_model.multi_class = "auto"

from member2.currentness_agent import run_currentness_verification
from member2.schemas import Member1Context
from member2.fusion import CATEGORY_COMPATIBILITY, CATEGORY_CONFLICT_THRESHOLD

from member4.authorization_service import authorize_response
from member4.schemas import VerificationRequest, FeedbackRequest, VerificationResponse
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


_MIME_TO_AUDIO_EXT = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/wave": ".wav",
    "audio/mp3": ".mp3",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/m4a": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/flac": ".flac",
    "audio/aac": ".aac",
    "audio/opus": ".opus",
}


def _validate_audio_upload(upload: UploadFile) -> str:
    """Validate audio upload by extension or MIME type, returning the proper file suffix."""
    ext = _ext(upload.filename)
    if ext in _AUDIO_EXTS:
        return ext
    # Fallback to content-type if filename lacks extension or is generic blob
    content_type = (upload.content_type or "").lower().split(";")[0].strip()
    if content_type in _MIME_TO_AUDIO_EXT:
        return _MIME_TO_AUDIO_EXT[content_type]
    raise HTTPException(
        status_code=415,
        detail=(
            f"Unsupported audio format '{ext or content_type}'. "
            f"Allowed audio formats: {sorted(_AUDIO_EXTS)}"
        ),
    )
_PLACEHOLDER_SUBMISSIONS = {
    "string",
    "placeholder",
    "n/a",
    "none",
    "null",
    "undefined",
    "sample",
    "demo",
}


def _is_placeholder_text(t: Optional[str]) -> bool:
    if not t:
        return False
    return t.strip().lower() in _PLACEHOLDER_SUBMISSIONS


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
    has_conflict = getattr(result, "has_conflict", False) or bool(result.conflicts_detected)
    return {
        "currentness": result.currentness.value,
        "confidence": result.confidence,
        "action": result.action.value,
        "has_conflict": has_conflict,
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


def _get_report_conflicts(report: Report) -> list[str]:
    """
    Returns detected conflicts from stored currentness assessment, or dynamically
    reconstructs category conflicts if not present in stored JSON.
    """
    conflicts: list[str] = []
    curr = report.currentness_assessment or {}
    stored_conflicts = curr.get("conflicts_detected")
    if stored_conflicts:
        conflicts.extend(stored_conflicts)
        return conflicts

    # Dynamic reconstruction for historical records
    m1 = report.crisis_analysis or {}
    text_type = str(m1.get("incident_type") or "").strip().lower()
    if not text_type or text_type in ("unknown", "other"):
        return conflicts

    evidence = curr.get("evidence") or []
    seen_visual_classes: set[str] = set()

    for item in evidence:
        details = item.get("details") or {}
        source = item.get("source", "")
        is_visual = (
            "classification" in source
            or source == "video"
            or "predicted_class" in details
        )
        if not is_visual or not details:
            continue

        pred_class = str(details.get("predicted_class") or "").strip().lower()
        if not pred_class or pred_class in seen_visual_classes:
            continue

        confidence = float(details.get("confidence") or item.get("weight") or 0.0)
        if confidence < CATEGORY_CONFLICT_THRESHOLD:
            continue

        compatible_types = CATEGORY_COMPATIBILITY.get(pred_class)
        if compatible_types is not None and text_type not in compatible_types:
            seen_visual_classes.add(pred_class)
            source_label = (
                f"Video frame {details['frame_index']} visual classifier"
                if "frame_index" in details
                else "Image visual classifier"
            )
            conflicts.append(
                f"Cross-modal category conflict: Citizen text indicates '{m1.get('incident_type')}' "
                f"(source: Citizen text NLP) while visual evidence indicates '{pred_class.title()}' "
                f"(source: {source_label}, confidence: {confidence:.1%}). "
                f"Incompatible incident categories: {text_type.title()} contradicts {pred_class.title()}. "
                f"Human verification is required."
            )

    return conflicts


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------



@app.get("/")
def home():
    return {"message": "CrisisSense API is running", "version": "2.0"}


# ── JSON text-only endpoint (backwards compatible) ───────────────────────────

class CrisisRequest(BaseModel):
    text: str
    location_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class RegisterRequest(BaseModel):
    full_name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class VerifyCodeRequest(BaseModel):
    email: str
    code: str


class ResendCodeRequest(BaseModel):
    email: str


class AdminInformationRequest(BaseModel):
    message: str


def _as_utc(dt):
    if dt is None:
        return utc_now()
    if getattr(dt, "tzinfo", None) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# ── Citizen Authentication Endpoints ─────────────────────────────────────────

@app.post("/auth/register", status_code=201)
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
):
    """Register a new citizen account with salted password hashing and email verification code."""
    try:
        normalized_email = validate_email_address(request.email)
        validate_password_strength(request.password)
    except ValueError as val_err:
        raise HTTPException(
            status_code=400,
            detail=str(val_err),
        )

    # Check for duplicate accounts
    existing_user = db.scalars(
        select(User).where(User.email == normalized_email)
    ).first()
    if existing_user is not None:
        raise HTTPException(
            status_code=409,
            detail="An account with this email address already exists.",
        )

    full_name = request.full_name.strip()
    if not full_name:
        raise HTTPException(
            status_code=400,
            detail="Full name cannot be empty.",
        )

    user = User(
        full_name=full_name,
        email=normalized_email,
        password_hash=hash_password(request.password),
        role="citizen",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Generate secure 6-digit verification code with 15-minute expiration
    raw_code = generate_verification_code()
    code_hash = hash_verification_code(raw_code)
    expires_at = utc_now() + timedelta(minutes=15)

    verif = db.scalar(
        select(AccountVerification).where(AccountVerification.email == normalized_email)
    )
    if verif is None:
        verif = AccountVerification(
            email=normalized_email,
            code_hash=code_hash,
            is_verified=False,
            expires_at=expires_at,
            attempts_count=0,
            resend_count=0,
            last_sent_at=utc_now(),
        )
        db.add(verif)
    else:
        verif.code_hash = code_hash
        verif.is_verified = False
        verif.expires_at = expires_at
        verif.attempts_count = 0
        verif.resend_count = 0
        verif.last_sent_at = utc_now()
    db.commit()

    # Dispatch verification code via email service
    send_verification_code_email(
        recipient_email=normalized_email,
        citizen_name=full_name,
        code=raw_code,
        expires_minutes=15,
    )

    token = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role,
            "is_verified": False,
        },
        "verification": {
            "status": "PENDING_VERIFICATION",
            "message": "A single-use verification code has been dispatched to your email address.",
            "expires_in_minutes": 15,
        },
    }


@app.post("/auth/verify-code")
def verify_email_code(
    request: VerifyCodeRequest,
    db: Session = Depends(get_db),
):
    """Verify citizen email address with a 6-digit one-time verification code."""
    try:
        normalized_email = validate_email_address(request.email)
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))

    candidate_code = request.code.strip()
    if not candidate_code:
        raise HTTPException(status_code=400, detail="Verification code cannot be empty.")

    user = db.scalar(select(User).where(User.email == normalized_email))
    if user is None:
        raise HTTPException(status_code=404, detail="No account found with this email.")

    verif = db.scalar(
        select(AccountVerification).where(AccountVerification.email == normalized_email)
    )

    if verif is None:
        # Legacy account: activate verification record
        verif = AccountVerification(
            email=normalized_email,
            code_hash="",
            is_verified=True,
            expires_at=utc_now(),
        )
        db.add(verif)
        db.commit()
        return {
            "status": "ALREADY_VERIFIED",
            "message": "Account email is already verified.",
            "is_verified": True,
            "user": {
                "id": user.id,
                "full_name": user.full_name,
                "email": user.email,
                "role": user.role,
                "is_verified": True,
            },
        }

    if verif.is_verified:
        return {
            "status": "ALREADY_VERIFIED",
            "message": "Account email is already verified.",
            "is_verified": True,
            "user": {
                "id": user.id,
                "full_name": user.full_name,
                "email": user.email,
                "role": user.role,
                "is_verified": True,
            },
        }

    # Brute-force guessing protection (max 5 attempts)
    if verif.attempts_count >= 5:
        raise HTTPException(
            status_code=429,
            detail="Too many failed verification attempts. Please request a new verification code.",
        )

    # Expiration check
    if utc_now() > _as_utc(verif.expires_at):
        raise HTTPException(
            status_code=400,
            detail="Verification code has expired. Please request a new code.",
        )

    # Code match verification
    if not verify_code_hash(candidate_code, verif.code_hash):
        verif.attempts_count += 1
        db.commit()
        remaining = max(0, 5 - verif.attempts_count)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid verification code. {remaining} attempt(s) remaining.",
        )

    # Invalidate code upon successful verification (one-time use)
    verif.is_verified = True
    verif.code_hash = ""
    verif.updated_at = utc_now()
    db.commit()

    token = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
    )

    return {
        "status": "VERIFIED",
        "message": "Account email successfully verified.",
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role,
            "is_verified": True,
        },
    }


@app.post("/auth/resend-code")
def resend_verification_code(
    request: ResendCodeRequest,
    db: Session = Depends(get_db),
):
    """Resend a fresh email verification code with cooldown and resend limits."""
    try:
        normalized_email = validate_email_address(request.email)
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))

    user = db.scalar(select(User).where(User.email == normalized_email))
    if user is None:
        raise HTTPException(status_code=404, detail="No account found with this email.")

    verif = db.scalar(
        select(AccountVerification).where(AccountVerification.email == normalized_email)
    )

    if verif and verif.is_verified:
        raise HTTPException(status_code=400, detail="This account is already verified.")

    # Enforce maximum resend limit (5)
    if verif and verif.resend_count >= 5:
        raise HTTPException(
            status_code=429,
            detail="Maximum resend limit (5) reached. Please try again later or contact support.",
        )

    # Enforce 30-second resend cooldown
    if verif and verif.last_sent_at and (utc_now() - _as_utc(verif.last_sent_at)).total_seconds() < 30:
        remaining_secs = int(30 - (utc_now() - _as_utc(verif.last_sent_at)).total_seconds())
        raise HTTPException(
            status_code=429,
            detail=f"Please wait {remaining_secs} seconds before requesting another code.",
        )

    raw_code = generate_verification_code()
    code_hash = hash_verification_code(raw_code)
    expires_at = utc_now() + timedelta(minutes=15)

    if not verif:
        verif = AccountVerification(
            email=normalized_email,
            code_hash=code_hash,
            is_verified=False,
            expires_at=expires_at,
            attempts_count=0,
            resend_count=1,
            last_sent_at=utc_now(),
        )
        db.add(verif)
    else:
        verif.code_hash = code_hash
        verif.expires_at = expires_at
        verif.attempts_count = 0
        verif.resend_count += 1
        verif.last_sent_at = utc_now()

    db.commit()

    send_verification_code_email(
        recipient_email=normalized_email,
        citizen_name=user.full_name,
        code=raw_code,
        expires_minutes=15,
    )

    return {
        "status": "SENT",
        "message": "A new verification code has been dispatched to your email.",
        "resend_count": verif.resend_count,
        "max_resends": 5,
        "expires_in_minutes": 15,
    }


@app.get("/auth/status")
def auth_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return user profile and current email verification status."""
    verif = db.scalar(
        select(AccountVerification).where(AccountVerification.email == current_user.email)
    )
    is_verified = verif.is_verified if verif is not None else True
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "is_verified": is_verified,
    }


@app.post("/auth/login")
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    """Authenticate a citizen using email and salted password hash verification."""
    try:
        normalized_email = validate_email_address(request.email)
    except ValueError as val_err:
        raise HTTPException(
            status_code=400,
            detail=str(val_err),
        )

    user = db.scalars(
        select(User).where(User.email == normalized_email)
    ).first()

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="No account found with this email. Please register for a citizen account.",
        )

    if not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
    )

    verif = db.scalar(
        select(AccountVerification).where(AccountVerification.email == normalized_email)
    )
    is_verified = verif.is_verified if verif is not None else True

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role,
            "is_verified": is_verified,
        },
    }


@app.post("/auth/admin/login")
def admin_login(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    """Authenticate an administrator using email and salted password hash verification."""
    try:
        normalized_email = validate_email_address(request.email)
    except ValueError as val_err:
        raise HTTPException(
            status_code=400,
            detail=str(val_err),
        )

    user = db.scalars(
        select(User).where(User.email == normalized_email)
    ).first()

    if user is None or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.role not in ("authority", "admin"):
        raise HTTPException(
            status_code=403,
            detail="Access denied: This account does not have administrator privileges.",
        )

    token = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role,
        },
    }


@app.get("/auth/me")
def get_profile(
    current_user: User = Depends(get_current_user),
):
    """Return profile details for the authenticated user."""
    return {
        "id": current_user.id,
        "full_name": current_user.full_name,
        "email": current_user.email,
        "role": current_user.role,
        "created_at": utc_timestamp(current_user.created_at),
    }


@app.post("/auth/logout")
def logout():
    """Stateless logout confirmation endpoint."""
    return {"message": "Logged out successfully"}


@app.get("/citizen/incidents")
def list_citizen_incidents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_citizen_user),
):
    """List all incidents submitted by the authenticated citizen."""
    statement = (
        select(Incident)
        .where(
            (Incident.citizen_id == current_user.id)
            | Incident.reports.any(Report.citizen_id == current_user.id)
        )
        .order_by(Incident.created_at.desc())
    )
    incidents = db.scalars(statement).unique().all()
    return [
        {
            "incident_id": inc.id,
            "incident_type": inc.incident_type,
            "location_name": inc.location_name,
            "severity": inc.severity,
            "verification_status": inc.verification_status,
            "status": inc.status,
            "admin_feedback": getattr(inc, "admin_feedback", None),
            "report_count": len(inc.reports) if inc.reports else 1,
            "needs": inc.needs or [],
            "created_at": utc_timestamp(inc.created_at),
            "updated_at": utc_timestamp(inc.updated_at),
        }
        for inc in incidents
    ]

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
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    require_authority(current_user)
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
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    require_authority(current_user)
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
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    if not request.text.strip():
        raise HTTPException(
            status_code=422,
            detail="Report text cannot be empty.",
        )

    if _is_placeholder_text(request.text):
        raise HTTPException(
            status_code=422,
            detail="Report text cannot be a default placeholder ('string', 'test', etc.). Please provide a genuine incident description.",
        )

    # Member 1: identify crisis details.
    m1_result = analyze_crisis(request.text)

    # If explicit location was provided, geocode/attach it
    if request.location_name and request.location_name.strip():
        explicit_loc = {
            "text": request.location_name.strip(),
            "location_type": "city",
            "display_name": request.location_name.strip(),
            "latitude": request.latitude,
            "longitude": request.longitude,
        }
        if request.latitude is None or request.longitude is None:
            from member1.location_extractor import geocode_location
            geocoded = geocode_location(request.location_name.strip())
            if geocoded:
                explicit_loc["latitude"] = geocoded.get("latitude")
                explicit_loc["longitude"] = geocoded.get("longitude")
                explicit_loc["display_name"] = geocoded.get("display_name")
        if "locations" not in m1_result or not isinstance(m1_result.get("locations"), list):
            m1_result["locations"] = []
        m1_result["locations"].insert(0, explicit_loc)

    m1_context = _build_member1_context(m1_result)

    # Member 2: assess currentness and collect evidence.
    currentness_result = run_currentness_verification(
        text=request.text,
        member1_context=m1_context,
    )
    currentness_data = _format_currentness(currentness_result)

    # Idempotency / duplicate protection: check if an identical report was submitted within 5 minutes
    cutoff = utc_now() - timedelta(minutes=5)
    recent_duplicate = db.scalars(
        select(Report)
        .where(Report.original_text == request.text, Report.received_at >= cutoff)
        .order_by(Report.received_at.desc())
    ).first()

    if recent_duplicate is not None:
        return {
            "report_id": recent_duplicate.id,
            "incident_id": recent_duplicate.incident_id,
            "storage_status": "EXISTING_DUPLICATE",
            "crisis_analysis": m1_result,
            "currentness": currentness_data,
            "is_duplicate": True,
            "has_conflict": len(currentness_data.get("conflicts_detected", [])) > 0,
            "conflicts_detected": currentness_data.get("conflicts_detected", []),
            "email_notification": {"status": "SKIPPED", "message": "Duplicate report; confirmation email already sent."},
        }

    # Member 3: preserve the original text and both outputs with citizen association.
    citizen_id = current_user.id if current_user else None
    report = save_report(
        db=db,
        original_text=request.text,
        crisis_analysis=m1_result,
        currentness_assessment=currentness_data,
        citizen_id=citizen_id,
    )

    create_incident_from_report(db=db, report=report)

    # Dispatch confirmation email if submitted by an authenticated citizen
    email_status = {"status": "SKIPPED", "message": "No citizen account linked."}
    if current_user and report.incident_id:
        loc_name = None
        if m1_result.get("locations"):
            loc_name = m1_result["locations"][0].get("text")
        email_res = send_incident_confirmation_email(
            recipient_email=current_user.email,
            citizen_name=current_user.full_name,
            incident_id=report.incident_id,
            incident_type=m1_result.get("incident_type") or "Crisis Incident",
            location_name=loc_name,
            submission_timestamp=utc_timestamp(report.received_at),
        )
        email_status = email_res.to_dict()

    return {
        "report_id": report.id,
        "incident_id": report.incident_id,
        "storage_status": "SAVED",
        "crisis_analysis": m1_result,
        "currentness": currentness_data,
        "has_conflict": len(currentness_data.get("conflicts_detected", [])) > 0,
        "conflicts_detected": currentness_data.get("conflicts_detected", []),
        "email_notification": email_status,
    }


# ── Multipart form-data endpoint (text + optional media uploads) ─────────────

@app.post("/analyze")
async def analyze(
    text: Optional[str] = Form(default=None),
    image: Optional[UploadFile] = File(default=None),
    video: Optional[UploadFile] = File(default=None),
    audio: Optional[UploadFile] = File(default=None),
    location_name: Optional[str] = Form(default=None),
    latitude: Optional[float] = Form(default=None),
    longitude: Optional[float] = Form(default=None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Multimodal /analyze endpoint.

    Accepts multipart/form-data with:
      - text          (form field, optional)
      - image         (file upload, optional)
      - video         (file upload, optional)
      - audio         (file upload, optional)
      - location_name (form field, optional)
      - latitude      (form field, optional)
      - longitude     (form field, optional)

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

    # Reject text-only placeholder submissions
    if has_text and not (has_image or has_video or has_audio) and _is_placeholder_text(text):
        raise HTTPException(
            status_code=422,
            detail="Report text cannot be a default placeholder ('string', 'test', etc.). Please provide a genuine incident description.",
        )

    # Validate file extensions before saving anything
    if has_image:
        _validate_ext(image.filename, _IMAGE_EXTS, "image")
    if has_video:
        _validate_ext(video.filename, _VIDEO_EXTS, "video")
    
    audio_suffix = ""
    if has_audio:
        audio_suffix = _validate_audio_upload(audio)
        audio.file.seek(0, os.SEEK_END)
        audio_size = audio.file.tell()
        audio.file.seek(0)
        if audio_size == 0:
            raise HTTPException(status_code=400, detail="Uploaded audio file is empty (0 bytes).")
        if audio_size > 50 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Audio file exceeds 50MB size limit.")

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
            audio_path = _save_upload(audio, suffix=audio_suffix)
            temp_paths.append(audio_path)

        # ── Step 1: collect raw text from every modality ─────────────────
        # Start with the form-provided text (if any).
        combined_text_parts: list[str] = []
        if text and text.strip():
            combined_text_parts.append(text.strip())

        # Extract text from the image via OCR (best-effort).
        if image_path:
            try:
                from member2.ocr import extract_ocr_text
                ocr_text = extract_ocr_text(image_path)
                if ocr_text and ocr_text.strip():
                    combined_text_parts.append(ocr_text.strip())
            except Exception as exc:
                print(f"[analyze] OCR extraction failed: {exc}")

        # Extract transcript from the audio via ASR.
        audio_transcription_result = None
        if audio_path:
            try:
                from member2.audio import transcribe_audio
                asr = transcribe_audio(audio_path)
                audio_transcription_result = {
                    "text": asr.full_text if getattr(asr, "succeeded", False) else "",
                    "succeeded": getattr(asr, "succeeded", False),
                    "language": getattr(asr, "language", None),
                    "duration": getattr(asr, "duration", None),
                    "error": getattr(asr, "error", None),
                }
                if getattr(asr, "succeeded", False) and asr.full_text.strip():
                    combined_text_parts.append(asr.full_text.strip())
            except Exception as exc:
                print(f"[analyze] Audio transcription failed: {exc}")
                audio_transcription_result = {
                    "text": "",
                    "succeeded": False,
                    "error": str(exc),
                }

        # If user submitted only audio and transcription failed with error
        if has_audio and not has_text and not has_image and not has_video:
            if not audio_transcription_result or not audio_transcription_result.get("succeeded"):
                err_msg = (audio_transcription_result or {}).get("error") or "Audio analysis could not decode intelligible speech."
                raise HTTPException(
                    status_code=422,
                    detail=f"Audio processing error: {err_msg}. Please provide a clear audio recording or enter a description.",
                )

        # Extract text from sampled video frames via OCR (best-effort).
        if video_path:
            try:
                from member2.video import sample_video_frames
                from member2.ocr import extract_ocr_text
                frames = sample_video_frames(video_path, max_frames=5)
                for frame in frames:
                    frame_ocr = extract_ocr_text(frame["image"])
                    if frame_ocr and frame_ocr.strip():
                        trimmed = frame_ocr.strip()
                        if trimmed not in combined_text_parts:
                            combined_text_parts.append(trimmed)
            except Exception as exc:
                print(f"[analyze] Video OCR extraction failed: {exc}")

        combined_text = " ".join(combined_text_parts).strip()

        # ── Step 2: Member 1 classifies the combined text ────────────────
        if combined_text:
            m1_result = analyze_crisis(combined_text)
        else:
            m1_result = {
                "is_crisis": None,
                "incident_type": None,
                "information_type": None,
                "severity": None,
                "needs": [],
                "locations": [],
                "crisis_probability": None,
                "message": (
                    "No text could be extracted from any modality. "
                    "Crisis analysis is unavailable for this submission."
                ),
            }

        # If explicit location was provided, geocode/attach it
        if location_name and location_name.strip():
            explicit_loc = {
                "text": location_name.strip(),
                "location_type": "city",
                "display_name": location_name.strip(),
                "latitude": latitude,
                "longitude": longitude,
            }
            if latitude is None or longitude is None:
                from member1.location_extractor import geocode_location
                geocoded = geocode_location(location_name.strip())
                if geocoded:
                    explicit_loc["latitude"] = geocoded.get("latitude")
                    explicit_loc["longitude"] = geocoded.get("longitude")
                    explicit_loc["display_name"] = geocoded.get("display_name")
            if "locations" not in m1_result or not isinstance(m1_result.get("locations"), list):
                m1_result["locations"] = []
            m1_result["locations"].insert(0, explicit_loc)

        m1_context = _build_member1_context(m1_result)

        # ── Step 3: Member 2 currentness verification ────────────────────
        # Pass the combined text so temporal claims from OCR/ASR are also
        # considered alongside the form text.
        currentness_result = run_currentness_verification(
            text=combined_text or None,
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
    storage_status = "NOT_SAVED_NO_TEXT"

    # Persist any submission that produced usable text —
    # whether from a form field, OCR, ASR, or a combination.
    if combined_text:
        # Idempotency / duplicate protection: check if identical text was submitted within the last 5 minutes
        cutoff = utc_now() - timedelta(minutes=5)
        recent_duplicate = db.scalars(
            select(Report)
            .where(Report.original_text == combined_text, Report.received_at >= cutoff)
            .order_by(Report.received_at.desc())
        ).first()

        if recent_duplicate is not None:
            report_id = recent_duplicate.id
            incident_id = recent_duplicate.incident_id
            storage_status = "EXISTING_DUPLICATE"
        else:
            citizen_id = current_user.id if current_user else None
            report = save_report(
                db=db,
                original_text=combined_text,
                crisis_analysis=m1_result,
                currentness_assessment=currentness_data,
                citizen_id=citizen_id,
            )

            create_incident_from_report(db=db, report=report)

            report_id = report.id
            incident_id = report.incident_id
            storage_status = "SAVED"

    email_status = {"status": "SKIPPED", "message": "No citizen account linked."}
    if current_user and incident_id and storage_status == "SAVED":
        loc_name = None
        if m1_result.get("locations"):
            loc_name = m1_result["locations"][0].get("text")
        email_res = send_incident_confirmation_email(
            recipient_email=current_user.email,
            citizen_name=current_user.full_name,
            incident_id=incident_id,
            incident_type=m1_result.get("incident_type") or "Crisis Incident",
            location_name=loc_name,
            submission_timestamp=utc_timestamp(utc_now()),
        )
        email_status = email_res.to_dict()

    return {
        "report_id": report_id,
        "incident_id": incident_id,
        "storage_status": storage_status,
        "crisis_analysis": m1_result,
        "currentness": currentness_data,
        "audio_transcription": audio_transcription_result,
        "has_conflict": currentness_data.get("has_conflict", False) or len(currentness_data.get("conflicts_detected", [])) > 0,
        "conflicts_detected": currentness_data.get("conflicts_detected", []),
        "email_notification": email_status,
    }

@app.get("/public/stats")
def get_public_stats(db: Session = Depends(get_db)):
    """Return aggregated response grid summary count for public landing page."""
    total_incidents = db.scalar(select(func.count(Incident.id))) or 0
    return {
        "total_incidents": total_incidents,
        "monitored_incidents": total_incidents,
        "grid_status": "ACTIVE",
    }


@app.get("/incidents")
def list_incidents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_authority_user),
):
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

    # Query all reports to determine conflict presence (stored or reconstructed)
    all_reports = db.scalars(
        select(Report).where(Report.incident_id.isnot(None))
    ).all()
    conflict_report_incidents = set()
    for rep in all_reports:
        if _get_report_conflicts(rep):
            conflict_report_incidents.add(rep.incident_id)

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
            "admin_feedback": getattr(incident, "admin_feedback", None),
            "report_count": report_count,
            "has_conflict": incident.id in conflict_report_incidents,
            "created_at": utc_timestamp(incident.created_at),
            "updated_at": utc_timestamp(incident.updated_at),
        }
        for incident, report_count in rows
    ]

@app.post("/incidents/{incident_id}/verify", response_model=VerificationResponse)
def verify_incident_endpoint(
    incident_id: str,
    request: VerificationRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    require_authority(current_user)
    result = verify_incident(
        db=db,
        incident_id=incident_id,
        decision=request.decision,
        reason=request.reason,
        admin_user=current_user,
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
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    incident = db.get(Incident, incident_id)

    if incident is None:
        raise HTTPException(
            status_code=404,
            detail="Incident not found.",
        )

    # Ownership & Authorization Check:
    # - Authority operators (role in 'authority', 'admin') are always authorized to inspect incidents.
    # - The owning citizen is authorized to inspect their own incident.
    # - Otherwise (unauthenticated, different citizen, or citizen attempting to access legacy unowned record),
    #   return 404 to preserve privacy and prevent unauthorized data inspection.
    is_authority = current_user is not None and current_user.role in ("authority", "admin")
    is_owner = (
        current_user is not None
        and (
            (incident.citizen_id is not None and current_user.id == incident.citizen_id)
            or any(r.citizen_id == current_user.id for r in incident.reports)
        )
    )
    if not (is_authority or is_owner):
        raise HTTPException(
            status_code=404,
            detail="Incident not found or unauthorized to view this record.",
        )

    reports = db.scalars(
        select(Report)
        .where(Report.incident_id == incident_id)
        .order_by(Report.received_at, Report.id)
    ).all()

    all_conflicts = []
    formatted_reports = []
    for report in reports:
        report_conflicts = _get_report_conflicts(report)
        for c in report_conflicts:
            if c not in all_conflicts:
                all_conflicts.append(c)

        curr_dict = dict(report.currentness_assessment or {})
        if report_conflicts:
            curr_dict["conflicts_detected"] = report_conflicts
            curr_dict["has_conflict"] = True
        else:
            curr_dict["has_conflict"] = curr_dict.get("has_conflict", False)

        formatted_reports.append({
            "report_id": report.id,
            "original_text": report.original_text,
            "crisis_analysis": report.crisis_analysis,
            "currentness": curr_dict,
            "received_at": utc_timestamp(report.received_at),
        })

    has_conflict = len(all_conflicts) > 0

    citizen_info = None
    if is_authority:
        target_citizen_id = incident.citizen_id
        if not target_citizen_id:
            for rep in reports:
                if rep.citizen_id:
                    target_citizen_id = rep.citizen_id
                    break

        if target_citizen_id:
            citizen_user = db.get(User, target_citizen_id)
            if citizen_user:
                citizen_info = {
                    "id": citizen_user.id,
                    "full_name": citizen_user.full_name or "Registered Citizen",
                    "email": citizen_user.email,
                    "role": citizen_user.role,
                    "is_anonymous": False,
                }
            else:
                citizen_info = {
                    "id": target_citizen_id,
                    "full_name": "Registered Citizen",
                    "email": "No linked citizen account",
                    "is_anonymous": False,
                }
        else:
            citizen_info = {
                "id": None,
                "full_name": "Anonymous submission",
                "email": "No linked citizen account",
                "is_anonymous": True,
            }

    response_data = {
        "incident_id": incident.id,
        "incident_type": incident.incident_type,
        "location_name": incident.location_name,
        "latitude": incident.latitude,
        "longitude": incident.longitude,
        "severity": incident.severity,
        "needs": incident.needs,
        "status": incident.status,
        "verification_status": incident.verification_status,
        "admin_feedback": getattr(incident, "admin_feedback", None),
        "has_conflict": has_conflict,
        "conflicts_detected": all_conflicts,
        "created_at": utc_timestamp(incident.created_at),
        "updated_at": utc_timestamp(incident.updated_at),
        "report_count": len(reports),
        "reports": formatted_reports,
    }
    if is_authority:
        response_data["submitting_citizen"] = citizen_info

    return response_data

class IncidentStatusUpdate(BaseModel):
    status: Literal["OPEN", "IN_PROGRESS", "RESOLVED"]


@app.patch("/incidents/{incident_id}/status")
def update_incident_status(
    incident_id: str,
    request: IncidentStatusUpdate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    require_authority(current_user)
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


@app.delete("/incidents/{incident_id}")
def delete_incident_endpoint(
    incident_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Permanently delete an incident and all its linked reports."""
    require_authority(current_user)
    deleted = delete_incident(db=db, incident_id=incident_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Incident not found.",
        )
    return {
        "success": True,
        "incident_id": incident_id,
        "message": f"Incident {incident_id} permanently deleted.",
    }


# ── Location Search Endpoint (Indian cities + global places) ────────────────

@app.get("/locations/search")
def search_locations(
    q: str = Query(..., min_length=2, description="Search term for city or location"),
):
    """
    Search for valid geographic locations (Indian cities and global places).
    Returns coordinates, city, state, country, and display name.
    Does not require device location permission.
    """
    from member1.location_extractor import (
        _CITY_REGISTRY,
        search_nominatim,
        convert_nominatim_result,
        normalize_text,
    )

    query_clean = q.strip()
    query_norm = normalize_text(query_clean)
    results = []
    seen_keys = set()

    # 1. Local registry lookup (fast, covers 80+ major Indian cities including Vijayawada, Jaisalmer, etc.)
    for city_name, state_name, lat, lon in _CITY_REGISTRY:
        city_norm = normalize_text(city_name)
        if query_norm in city_norm or city_norm in query_norm:
            key = (round(lat, 3), round(lon, 3))
            if key not in seen_keys:
                seen_keys.add(key)
                results.append({
                    "display_name": f"{city_name}, {state_name}, India",
                    "city": city_name,
                    "state": state_name,
                    "country": "India",
                    "latitude": float(lat),
                    "longitude": float(lon),
                    "source": "local_registry",
                })

    # 2. Supplementary geocoding search for other locations
    if len(results) < 5:
        try:
            nom_results = search_nominatim(query_clean, location_type="city")
            for item in nom_results:
                converted = convert_nominatim_result(item, query_clean, "city")
                if converted:
                    lat = round(float(converted["latitude"]), 3)
                    lon = round(float(converted["longitude"]), 3)
                    key = (lat, lon)
                    if key not in seen_keys:
                        seen_keys.add(key)
                        results.append({
                            "display_name": converted.get("display_name") or f"{converted.get('city', '')}, {converted.get('state', '')}, {converted.get('country', '')}",
                            "city": converted.get("city") or query_clean.title(),
                            "state": converted.get("state") or "",
                            "country": converted.get("country") or "",
                            "latitude": float(converted["latitude"]),
                            "longitude": float(converted["longitude"]),
                            "source": "nominatim",
                        })
                        if len(results) >= 10:
                            break
        except Exception as exc:
            print(f"[locations/search] Nominatim query error: {exc}")

    return {
        "query": query_clean,
        "count": len(results),
        "results": results,
    }


# ── Admin-to-Citizen Information Request Endpoint ───────────────────────────

@app.post("/incidents/{incident_id}/request-info")
def request_citizen_info(
    incident_id: str,
    request: AdminInformationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_authority_user),
):
    """
    Allow authorized emergency authority / admin to request additional information from
    the specific citizen who submitted an incident.
    Enforces admin authorization, validates citizen email, and provides delivery feedback.
    """
    message = request.message.strip()
    if not message:
        raise HTTPException(
            status_code=400,
            detail="Information request message cannot be empty.",
        )

    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(
            status_code=404,
            detail="Incident not found.",
        )

    # Resolve linked citizen
    citizen = None
    if incident.citizen_id:
        citizen = db.get(User, incident.citizen_id)

    if citizen is None:
        for rep in incident.reports:
            if rep.citizen_id:
                citizen = db.get(User, rep.citizen_id)
                if citizen:
                    break

    if citizen is None or not citizen.email:
        raise HTTPException(
            status_code=400,
            detail="This incident was submitted anonymously or without an associated citizen account. Direct information requests cannot be dispatched.",
        )

    email_res = send_admin_information_request_email(
        recipient_email=citizen.email,
        citizen_name=citizen.full_name or "Citizen",
        incident_id=incident.id,
        request_message=message,
        admin_name=current_user.full_name or "Emergency Operations Command",
    )

    if not email_res.success:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to dispatch information request email: {email_res.error}",
        )

    email_parts = citizen.email.split("@")
    if len(email_parts) == 2 and len(email_parts[0]) > 2:
        masked_email = f"{email_parts[0][:2]}***@{email_parts[1]}"
    else:
        masked_email = f"***@{email_parts[-1]}" if len(email_parts) == 2 else "***"

    return {
        "status": "DISPATCHED",
        "message": f"Information request dispatched to citizen ({masked_email}).",
        "incident_id": incident.id,
        "recipient_name": citizen.full_name,
        "recipient_email_masked": masked_email,
        "dispatched_at": utc_now().isoformat(),
    }


# ── Analytics and Metrics Endpoint (Real Application Data) ──────────────────

@app.get("/analytics/metrics")
def get_analytics_metrics(
    db: Session = Depends(get_db),
):
    """
    Return comprehensive crisis intelligence metrics computed directly from real database records.
    Safely handles empty datasets without introducing fake records.
    """
    total_incidents = db.scalar(select(func.count(Incident.id))) or 0
    total_reports = db.scalar(select(func.count(Report.id))) or 0

    if total_incidents == 0:
        return {
            "total_incidents": 0,
            "total_reports": 0,
            "severity_distribution": {},
            "status_distribution": {},
            "verification_distribution": {},
            "incident_types": {},
            "timeline": [],
        }

    # Severity distribution
    severity_rows = db.execute(
        select(Incident.severity, func.count(Incident.id))
        .group_by(Incident.severity)
    ).all()
    severity_distribution = {
        (row[0] or "UNKNOWN").upper(): row[1] for row in severity_rows
    }

    # Status distribution
    status_rows = db.execute(
        select(Incident.status, func.count(Incident.id))
        .group_by(Incident.status)
    ).all()
    status_distribution = {
        (row[0] or "OPEN").upper(): row[1] for row in status_rows
    }

    # Verification status distribution
    verif_rows = db.execute(
        select(Incident.verification_status, func.count(Incident.id))
        .group_by(Incident.verification_status)
    ).all()
    verification_distribution = {
        (row[0] or "PENDING").upper(): row[1] for row in verif_rows
    }

    # Incident types distribution
    type_rows = db.execute(
        select(Incident.incident_type, func.count(Incident.id))
        .group_by(Incident.incident_type)
        .order_by(func.count(Incident.id).desc())
    ).all()
    incident_types = {
        (row[0] or "Unknown"): row[1] for row in type_rows
    }

    # Timeline trends (by date)
    timeline_rows = db.execute(
        select(func.date(Incident.created_at), func.count(Incident.id))
        .group_by(func.date(Incident.created_at))
        .order_by(func.date(Incident.created_at).asc())
    ).all()
    timeline = [
        {"date": str(row[0]), "count": row[1]} for row in timeline_rows if row[0]
    ]

    return {
        "total_incidents": total_incidents,
        "total_reports": total_reports,
        "severity_distribution": severity_distribution,
        "status_distribution": status_distribution,
        "verification_distribution": verification_distribution,
        "incident_types": incident_types,
        "timeline": timeline,
    }
