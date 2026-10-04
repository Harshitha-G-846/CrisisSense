"""
currentness_agent.py  —  Member 2 / Phase 9
Currentness Verification Agent: multimodal evidence orchestration pipeline.

This module provides the central entry point for Member 2 multimodal currentness
verification. It orchestrates the deterministic feature extractors (temporal,
OCR, video, audio, perceptual reuse, reference corpus) and feeds their combined
evidence items into Phase 8 evidence fusion.

Pipeline:
    Inputs (text, image, video, audio, context, reference date, reuse corpus)
        ↓
    1. Text          → temporal.extract_temporal_evidence()
                       + reference.extract_reference_evidence()
    2. Image         → ocr.extract_image_evidence()
                       + reuse.check_image_reuse() (if reuse_corpus provided)
    3. Video         → video.extract_video_evidence()
                       + reuse.check_video_frames_reuse() (if reuse_corpus provided)
    4. Audio         → audio.extract_audio_evidence()
    5. Aggregation   → Combine all extracted EvidenceItem objects
        ↓
    6. Fusion        → fusion.fuse_evidence()
        ↓
    CurrentnessResult (verdict, confidence, action, evidence list, conflicts)
"""

from __future__ import annotations

import os
from datetime import date, datetime, timezone
from typing import Dict, List, Optional, Union

from .audio import extract_audio_evidence
from .fusion import fuse_evidence
from .ocr import extract_image_evidence, load_image
from .reference import extract_reference_evidence
from .reuse import ReuseCorpus, check_image_reuse, check_video_frames_reuse
from .schemas import (
    CurrentnessResult,
    CurrentnessVerdict,
    EvidenceItem,
    EvidenceSource,
    Member1Context,
    VerificationAction,
)
from .temporal import extract_temporal_evidence
from .video import extract_video_evidence, sample_video_frames


def _normalize_reference_date(reference_date: Optional[Union[date, datetime, str]]) -> date:
    """Safely normalizes optional reference date into a date object."""
    if reference_date is None:
        return datetime.now(timezone.utc).date()
    if isinstance(reference_date, datetime):
        return reference_date.date()
    if isinstance(reference_date, date):
        return reference_date
    if isinstance(reference_date, str):
        try:
            return date.fromisoformat(reference_date.strip())
        except Exception:
            return datetime.now(timezone.utc).date()
    return datetime.now(timezone.utc).date()


def run_currentness_verification(
    text: Optional[str] = None,
    image_path: Optional[Union[str, os.PathLike]] = None,
    video_path: Optional[Union[str, os.PathLike]] = None,
    audio_path: Optional[Union[str, os.PathLike]] = None,
    member1_context: Optional[Member1Context] = None,
    reference_date: Optional[Union[date, datetime, str]] = None,
    reuse_corpus: Optional[ReuseCorpus] = None,
    # Lightweight test/mock injection hooks to prevent network or live model dependencies
    transcript_override: Optional[str] = None,
    ocr_text_override: Optional[str] = None,
    video_ocr_override_per_frame: Optional[Dict[int, str]] = None,
) -> CurrentnessResult:
    """
    Orchestrates multimodal currentness evidence extraction and fusion.

    Parameters
    ----------
    text : Optional raw crisis text / caption / post body.
    image_path : Optional path to a local crisis image.
    video_path : Optional path to a local crisis video.
    audio_path : Optional path to a local crisis audio recording.
    member1_context : Optional upstream context from Member 1 (incident type, etc.).
    reference_date : Optional reference date for relative temporal claims (defaults to UTC today).
    reuse_corpus : Optional ReuseCorpus for perceptual hash matching of images/frames.
    transcript_override : Optional transcript string to bypass Whisper model execution in tests.
    ocr_text_override : Optional OCR text string to bypass Tesseract in tests.
    video_ocr_override_per_frame : Optional mapping of frame_index -> OCR text override.

    Returns
    -------
    CurrentnessResult : Final fused currentness verdict, confidence, action, and full evidence provenance.
    """
    ref_date = _normalize_reference_date(reference_date)
    all_evidence: List[EvidenceItem] = []

    # ------------------------------------------------------------------
    # 1. Text modality (temporal claims + historical event corpus matching)
    # ------------------------------------------------------------------
    if text is not None and isinstance(text, str) and text.strip():
        text_temporal_items = extract_temporal_evidence(
            text=text,
            reference_date=ref_date,
            source=EvidenceSource.TEXT,
        )
        all_evidence.extend(text_temporal_items)

        # Contextual reference corpus verification against CrisisLex historical events
        ref_items = extract_reference_evidence(
            text=text,
            temporal_items=text_temporal_items,
            member1_context=member1_context,
        )
        all_evidence.extend(ref_items)

    # ------------------------------------------------------------------
    # 2. Image modality (metadata/EXIF + visual OCR + optional reuse)
    # ------------------------------------------------------------------
    if image_path is not None:
        image_evidence = extract_image_evidence(
            image_input=image_path,
            reference_date=ref_date,
            ocr_text_override=ocr_text_override,
        )
        all_evidence.extend(image_evidence)

        # Perceptual reuse detection if reuse corpus is provided
        if reuse_corpus is not None and len(reuse_corpus) > 0:
            pil_img = load_image(image_path)
            if pil_img is not None:
                lbl = os.path.basename(str(image_path)) if isinstance(image_path, (str, os.PathLike)) else "image"
                reuse_item = check_image_reuse(
                    image=pil_img,
                    corpus=reuse_corpus,
                    label=lbl,
                )
                all_evidence.append(reuse_item)

    # ------------------------------------------------------------------
    # 3. Video modality (structural metadata + sampled frame OCR + reuse)
    # ------------------------------------------------------------------
    if video_path is not None:
        video_evidence = extract_video_evidence(
            video_path=video_path,
            reference_date=ref_date,
            max_frames=3,
            ocr_text_override_per_frame=video_ocr_override_per_frame,
        )
        all_evidence.extend(video_evidence)

        # Perceptual reuse detection on sampled video frames if reuse corpus is provided
        if reuse_corpus is not None and len(reuse_corpus) > 0:
            sampled_frames = sample_video_frames(video_path=video_path, max_frames=3)
            if sampled_frames:
                frame_reuse_items = check_video_frames_reuse(
                    frames=sampled_frames,
                    corpus=reuse_corpus,
                )
                all_evidence.extend(frame_reuse_items)

    # ------------------------------------------------------------------
    # 4. Audio modality (speech-to-text / transcript temporal claims)
    # ------------------------------------------------------------------
    if audio_path is not None or transcript_override is not None:
        audio_evidence = extract_audio_evidence(
            audio_path=audio_path or "",
            reference_date=ref_date,
            _transcript_override=transcript_override,
        )
        all_evidence.extend(audio_evidence)

    # ------------------------------------------------------------------
    # 5. Multimodal evidence fusion
    # ------------------------------------------------------------------
    return fuse_evidence(
        evidence=all_evidence,
        member1_context=member1_context,
    )
