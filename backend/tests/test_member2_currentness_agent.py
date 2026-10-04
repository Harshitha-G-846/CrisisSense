"""
test_member2_currentness_agent.py  —  Phase 9 tests
Tests the complete multimodal orchestration pipeline in member2/currentness_agent.py.
All tests are offline, deterministic, and use synthetic/mock fixtures (no Whisper downloads, no network).
"""

from __future__ import annotations

import os
from datetime import date
import numpy as np
import pytest
from PIL import Image
import cv2

from member2.currentness_agent import run_currentness_verification
from member2.reuse import ReuseCorpus
from member2.schemas import (
    CurrentnessResult,
    CurrentnessVerdict,
    EvidencePolarity,
    EvidenceSource,
    Member1Context,
    VerificationAction,
)

REF_DATE = date(2026, 10, 4)


# ---------------------------------------------------------------------------
# Helpers for synthetic fixtures
# ---------------------------------------------------------------------------

def _make_image(path: str, color=(200, 50, 50), size=(100, 100)) -> str:
    img = Image.new("RGB", size, color=color)
    img.save(path)
    return path


def _make_video(path: str, num_frames: int = 10, fps: float = 10.0, size=(160, 120)) -> str:
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    out = cv2.VideoWriter(path, fourcc, fps, size)
    for i in range(num_frames):
        frame = np.zeros((size[1], size[0], 3), dtype=np.uint8)
        frame[:, :] = (i * 15 % 255, 80, 140)
        out.write(frame)
    out.release()
    return path


# ---------------------------------------------------------------------------
# 1. Text with OLD temporal evidence → OLD
# ---------------------------------------------------------------------------

def test_text_old_temporal_evidence_produces_old():
    result = run_currentness_verification(
        text="The devastating earthquake happened in 2021 and destroyed houses.",
        reference_date=REF_DATE,
    )
    assert isinstance(result, CurrentnessResult)
    assert result.currentness == CurrentnessVerdict.OLD
    assert any(e.polarity == EvidencePolarity.OLD for e in result.evidence)
    assert any(e.source == EvidenceSource.TEXT for e in result.evidence)


# ---------------------------------------------------------------------------
# 2. Text with CURRENT temporal evidence → CURRENT
# ---------------------------------------------------------------------------

def test_text_current_temporal_evidence_produces_current():
    result = run_currentness_verification(
        text="Breaking news: major wildfire is happening right now in northern hills!",
        reference_date=REF_DATE,
    )
    assert isinstance(result, CurrentnessResult)
    assert result.currentness == CurrentnessVerdict.CURRENT
    assert any(e.polarity == EvidencePolarity.CURRENT for e in result.evidence)
    assert any(e.source == EvidenceSource.TEXT for e in result.evidence)


# ---------------------------------------------------------------------------
# 3. No temporal evidence → UNCERTAIN + HUMAN_VERIFICATION_REQUIRED
# ---------------------------------------------------------------------------

def test_no_temporal_evidence_produces_uncertain():
    # Text with zero temporal mentions
    result = run_currentness_verification(
        text="People are walking around the park with their dogs.",
        reference_date=REF_DATE,
    )
    assert result.currentness == CurrentnessVerdict.UNCERTAIN
    assert result.action == VerificationAction.HUMAN_VERIFICATION_REQUIRED
    assert result.conflicts_detected == []


def test_completely_empty_input_produces_uncertain():
    # No modalities supplied at all
    result = run_currentness_verification()
    assert result.currentness == CurrentnessVerdict.UNCERTAIN
    assert result.action == VerificationAction.HUMAN_VERIFICATION_REQUIRED
    assert result.confidence == 0.0
    assert result.evidence == []
    assert result.conflicts_detected == []


# ---------------------------------------------------------------------------
# 4. Image OCR temporal evidence reaches fusion
# ---------------------------------------------------------------------------

def test_image_ocr_temporal_evidence_reaches_fusion(tmp_path):
    img_path = str(tmp_path / "news_broadcast.png")
    _make_image(img_path)

    result = run_currentness_verification(
        image_path=img_path,
        ocr_text_override="LIVE BROADCAST: Flood waters rising fast today October 4, 2026",
        reference_date=REF_DATE,
    )
    assert any(e.source == EvidenceSource.OCR for e in result.evidence)
    assert result.currentness == CurrentnessVerdict.CURRENT


# ---------------------------------------------------------------------------
# 5. Video evidence reaches fusion
# ---------------------------------------------------------------------------

def test_video_evidence_reaches_fusion(tmp_path):
    vid_path = str(tmp_path / "crisis_clip.avi")
    _make_video(vid_path, num_frames=12)

    result = run_currentness_verification(
        video_path=vid_path,
        video_ocr_override_per_frame={
            0: "Archive footage from 2018 flood incident in the valley",
        },
        reference_date=REF_DATE,
    )
    assert any(e.source == EvidenceSource.METADATA for e in result.evidence)
    assert any(e.source == EvidenceSource.OCR for e in result.evidence)
    assert result.currentness == CurrentnessVerdict.OLD


# ---------------------------------------------------------------------------
# 6. Audio evidence reaches fusion using transcript override / mock
# ---------------------------------------------------------------------------

def test_audio_evidence_reaches_fusion_with_transcript_override():
    result = run_currentness_verification(
        audio_path="dummy_audio.wav",
        transcript_override="Reports confirm the dam collapsed just an hour ago today.",
        reference_date=REF_DATE,
    )
    assert any(e.source == EvidenceSource.AUDIO for e in result.evidence)
    assert result.currentness == CurrentnessVerdict.CURRENT


def test_audio_evidence_old_claim_reaches_fusion():
    result = run_currentness_verification(
        transcript_override="This recording was taken back during the 2019 cyclone.",
        reference_date=REF_DATE,
    )
    audio_items = [e for e in result.evidence if e.source == EvidenceSource.AUDIO]
    assert len(audio_items) >= 1
    assert audio_items[0].polarity == EvidencePolarity.OLD
    assert result.currentness == CurrentnessVerdict.OLD


# ---------------------------------------------------------------------------
# 7. Reuse match is included
# ---------------------------------------------------------------------------

def test_reuse_match_is_included(tmp_path):
    # Create known old crisis image in corpus
    corpus = ReuseCorpus()
    known_path = str(tmp_path / "known_old_disaster.png")
    _make_image(known_path, color=(10, 150, 10))
    corpus.add_image_file(known_path, label="known_disaster_2015")

    # Query with identical image
    query_path = str(tmp_path / "query_post.png")
    _make_image(query_path, color=(10, 150, 10))

    result = run_currentness_verification(
        image_path=query_path,
        ocr_text_override="Photo shared on social media",
        reuse_corpus=corpus,
        reference_date=REF_DATE,
    )

    reuse_items = [e for e in result.evidence if e.source == EvidenceSource.REUSE]
    assert len(reuse_items) >= 1
    assert any(r.polarity == EvidencePolarity.OLD for r in reuse_items)
    # Reuse alone requires human verification
    assert result.action == VerificationAction.HUMAN_VERIFICATION_REQUIRED


# ---------------------------------------------------------------------------
# 8. Multiple modalities are combined
# ---------------------------------------------------------------------------

def test_multiple_modalities_combined(tmp_path):
    img_path = str(tmp_path / "fire.png")
    _make_image(img_path)

    result = run_currentness_verification(
        text="Wildfire advancing towards suburban perimeter happening right now.",
        image_path=img_path,
        ocr_text_override="URGENT: Evacuation underway today",
        transcript_override="Emergency teams are deployed on the ground right now.",
        reference_date=REF_DATE,
    )

    sources = {e.source for e in result.evidence}
    assert EvidenceSource.TEXT in sources
    assert EvidenceSource.OCR in sources
    assert EvidenceSource.AUDIO in sources
    assert result.currentness == CurrentnessVerdict.CURRENT
    assert result.action == VerificationAction.ALLOW
    assert result.confidence >= 0.55


# ---------------------------------------------------------------------------
# 9. Conflicting modalities → UNCERTAIN + human verification
# ---------------------------------------------------------------------------

def test_conflicting_modalities_produces_uncertain(tmp_path):
    img_path = str(tmp_path / "conflict.png")
    _make_image(img_path)

    # Text claims happening right now (CURRENT) while OCR shows 2019 (OLD)
    result = run_currentness_verification(
        text="Breaking: flood waters breaching barriers right now!",
        image_path=img_path,
        ocr_text_override="Archive News Broadcast - June 2019",
        reference_date=REF_DATE,
    )

    assert result.currentness == CurrentnessVerdict.UNCERTAIN
    assert result.action == VerificationAction.HUMAN_VERIFICATION_REQUIRED
    assert len(result.conflicts_detected) >= 1


# ---------------------------------------------------------------------------
# 10. Missing / invalid media does not crash
# ---------------------------------------------------------------------------

def test_missing_or_invalid_media_does_not_crash(tmp_path):
    # Non-existent files passed across all modalities
    result = run_currentness_verification(
        text="Valid text with event details happening today",
        image_path=str(tmp_path / "does_not_exist.png"),
        video_path=str(tmp_path / "does_not_exist.mp4"),
        audio_path=str(tmp_path / "does_not_exist.wav"),
        reference_date=REF_DATE,
    )

    assert isinstance(result, CurrentnessResult)
    # The valid text should still be processed successfully
    assert any(e.source == EvidenceSource.TEXT and e.polarity == EvidencePolarity.CURRENT for e in result.evidence)
    # Missing media emits neutral error/warning evidence rather than crashing
    assert any(e.source == EvidenceSource.METADATA for e in result.evidence)
    assert any(e.source == EvidenceSource.AUDIO for e in result.evidence)


# ---------------------------------------------------------------------------
# 11. Member1Context is preserved in result
# ---------------------------------------------------------------------------

def test_member1_context_is_preserved():
    ctx = Member1Context(
        is_crisis=True,
        incident_type="flood",
        severity="critical",
        needs=["rescue", "boats"],
        locations=[{"name": "Kerala"}],
    )

    result = run_currentness_verification(
        text="Flood rescue operations happening today.",
        member1_context=ctx,
        reference_date=REF_DATE,
    )

    assert result.member1_context is not None
    assert result.member1_context.incident_type == "flood"
    assert result.member1_context.severity == "critical"
    assert result.member1_context.needs == ["rescue", "boats"]
    assert result.member1_context.locations == [{"name": "Kerala"}]


# ---------------------------------------------------------------------------
# 12. Evidence provenance is preserved
# ---------------------------------------------------------------------------

def test_evidence_provenance_is_preserved(tmp_path):
    img_path = str(tmp_path / "provenance.png")
    _make_image(img_path)

    result = run_currentness_verification(
        text="Disaster occurred in 2021.",
        image_path=img_path,
        ocr_text_override="Photo timestamp: 2021-06-12",
        transcript_override="The disaster was recorded in 2021.",
        reference_date=REF_DATE,
    )

    # Every item must have source, finding, polarity, and weight
    assert len(result.evidence) >= 3
    for ev in result.evidence:
        assert ev.source in EvidenceSource.__members__.values()
        assert isinstance(ev.finding, str) and len(ev.finding) > 0
        assert ev.polarity in EvidencePolarity.__members__.values()
        assert 0.0 <= ev.weight <= 1.0


# ---------------------------------------------------------------------------
# 13. Reference date parameter handling
# ---------------------------------------------------------------------------

def test_reference_date_iso_string_and_datetime():
    result_str = run_currentness_verification(
        text="Happened yesterday.",
        reference_date="2026-10-04",
    )
    assert any(e.polarity == EvidencePolarity.CURRENT for e in result_str.evidence)


# ---------------------------------------------------------------------------
# Task 3: Explicit Scenario Tests
# ---------------------------------------------------------------------------

def test_text_says_today_produces_current_evidence():
    result = run_currentness_verification(
        text="Flood waters reached danger levels today",
        reference_date=REF_DATE,
    )
    assert result.currentness == CurrentnessVerdict.CURRENT
    current_items = [e for e in result.evidence if e.polarity == EvidencePolarity.CURRENT]
    assert len(current_items) >= 1
    assert current_items[0].source == EvidenceSource.TEXT


def test_text_says_in_2021_produces_old_evidence():
    result = run_currentness_verification(
        text="The explosion in 2021 killed dozens of workers",
        reference_date=REF_DATE,
    )
    assert result.currentness == CurrentnessVerdict.OLD
    old_items = [e for e in result.evidence if e.polarity == EvidencePolarity.OLD]
    assert len(old_items) >= 1
    assert old_items[0].source == EvidenceSource.TEXT


def test_ocr_contains_old_date_produces_old(tmp_path):
    img_path = str(tmp_path / "old_date_ocr.png")
    _make_image(img_path)
    result = run_currentness_verification(
        image_path=img_path,
        ocr_text_override="Archived incident report: 15 March 2017",
        reference_date=REF_DATE,
    )
    assert result.currentness == CurrentnessVerdict.OLD
    assert any(e.source == EvidenceSource.OCR and e.polarity == EvidencePolarity.OLD for e in result.evidence)


def test_strong_current_evidence_produces_current():
    result = run_currentness_verification(
        text="Breaking emergency: Flash flood happening now in city center today!",
        reference_date=REF_DATE,
    )
    assert result.currentness == CurrentnessVerdict.CURRENT
    assert result.action == VerificationAction.ALLOW
    assert result.confidence >= 0.55


def test_strong_old_evidence_produces_old():
    result = run_currentness_verification(
        text="Historical footage from the 2018 cyclone disaster in Tamil Nadu.",
        transcript_override="This entire event occurred in 2018.",
        reference_date=REF_DATE,
    )
    assert result.currentness == CurrentnessVerdict.OLD
    assert result.action == VerificationAction.ALLOW
    assert result.confidence >= 0.55

