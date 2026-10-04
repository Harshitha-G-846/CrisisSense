"""
main.py — CrisisSense FastAPI backend
Member 1 (crisis analysis) + Member 2 (multimodal currentness verification)

/analyze accepts both:
  - JSON body  (text-only, backwards compatible)
  - multipart/form-data  (text + optional image/video/audio)
"""

from __future__ import annotations

import os
import tempfile
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from member1.pipeline import analyze_crisis
from member2.currentness_agent import run_currentness_verification
from member2.schemas import Member1Context


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


@app.post("/analyze-text")
def analyze_text(request: CrisisRequest):
    """
    Backwards-compatible text-only endpoint (JSON body).
    Returns Member 1 crisis analysis + Member 2 currentness verification.
    """
    m1_result = analyze_crisis(request.text)
    m1_context = _build_member1_context(m1_result)

    currentness_result = run_currentness_verification(
        text=request.text,
        member1_context=m1_context,
    )

    return {
        "crisis_analysis": m1_result,
        "currentness": _format_currentness(currentness_result),
    }


# ── Multipart form-data endpoint (text + optional media uploads) ─────────────

@app.post("/analyze")
async def analyze(
    text: Optional[str] = Form(default=None),
    image: Optional[UploadFile] = File(default=None),
    video: Optional[UploadFile] = File(default=None),
    audio: Optional[UploadFile] = File(default=None),
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

    return {
        "crisis_analysis": m1_result,
        "currentness": _format_currentness(currentness_result),
    }