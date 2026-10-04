import os
from datetime import date
import numpy as np
import pytest
import cv2

from member2.schemas import EvidenceItem, EvidencePolarity, EvidenceSource
from member2.video import (
    get_video_metadata,
    sample_video_frames,
    extract_video_evidence
)

REF_DATE = date(2026, 10, 3)


def create_synthetic_video(file_path: str, num_frames: int = 15, fps: float = 10.0, size: tuple = (160, 120)) -> str:
    """Helper to generate a small synthetic video using OpenCV MJPG format."""
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    out = cv2.VideoWriter(file_path, fourcc, fps, size)
    for i in range(num_frames):
        # Create a simple frame with a gradient or color
        frame = np.zeros((size[1], size[0], 3), dtype=np.uint8)
        frame[:, :] = (i * 10 % 255, 100, 150)
        out.write(frame)
    out.release()
    return file_path


def test_video_metadata_valid(tmp_path):
    video_path = str(tmp_path / "test_valid.avi")
    create_synthetic_video(video_path, num_frames=20, fps=10.0, size=(160, 120))

    meta = get_video_metadata(video_path)
    assert meta["is_valid"] is True
    assert meta["frame_count"] == 20
    assert meta["fps"] == 10.0
    assert meta["width"] == 160
    assert meta["height"] == 120
    assert meta["duration_seconds"] == 2.0


def test_video_metadata_invalid_and_missing(tmp_path):
    missing_meta = get_video_metadata(str(tmp_path / "non_existent.mp4"))
    assert missing_meta["is_valid"] is False
    assert missing_meta["frame_count"] == 0

    assert get_video_metadata("")["is_valid"] is False
    assert get_video_metadata(None)["is_valid"] is False  # type: ignore


def test_frame_sampling_subset(tmp_path):
    video_path = str(tmp_path / "test_sample.avi")
    # 30 frames total
    create_synthetic_video(video_path, num_frames=30, fps=10.0, size=(100, 100))

    sampled = sample_video_frames(video_path, max_frames=3)
    assert len(sampled) == 3
    # Check that it sampled a subset, not all 30 frames
    indices = [item["frame_index"] for item in sampled]
    assert indices == [0, 14, 29]
    assert all("image" in item for item in sampled)
    assert all("timestamp_seconds" in item for item in sampled)


def test_frame_sampling_short_video(tmp_path):
    video_path = str(tmp_path / "test_single_frame.avi")
    # 1 frame total
    create_synthetic_video(video_path, num_frames=1, fps=10.0, size=(100, 100))

    sampled = sample_video_frames(video_path, max_frames=3)
    # Only 1 unique frame available, should not crash with duplicates
    assert len(sampled) == 1
    assert sampled[0]["frame_index"] == 0


def test_video_evidence_old_ocr(tmp_path):
    video_path = str(tmp_path / "video_old.avi")
    create_synthetic_video(video_path, num_frames=10, fps=5.0)

    # Frame 0 has historical claim
    evidence = extract_video_evidence(
        video_path=video_path,
        reference_date=REF_DATE,
        max_frames=3,
        ocr_text_override_per_frame={0: "Flood on June 12, 2021 destroyed highway"}
    )

    assert len(evidence) >= 2
    sources = [e.source for e in evidence]
    assert EvidenceSource.METADATA in sources
    assert EvidenceSource.OCR in sources

    old_items = [e for e in evidence if e.polarity == EvidencePolarity.OLD]
    assert len(old_items) >= 1
    assert "2021-06-12" in str(old_items[0].details.get("date"))
    assert old_items[0].details.get("frame_index") == 0


def test_video_evidence_current_ocr(tmp_path):
    video_path = str(tmp_path / "video_current.avi")
    create_synthetic_video(video_path, num_frames=10, fps=5.0)

    # Middle frame has current claim
    evidence = extract_video_evidence(
        video_path=video_path,
        reference_date=REF_DATE,
        max_frames=3,
        ocr_text_override_per_frame={4: "Breaking: Fire happening today near Whitefield"}
    )

    current_items = [e for e in evidence if e.polarity == EvidencePolarity.CURRENT]
    assert len(current_items) >= 1
    assert "today" in current_items[0].finding.lower()
    assert current_items[0].details.get("frame_index") == 4


def test_video_evidence_neutral_when_no_temporal_text(tmp_path):
    video_path = str(tmp_path / "video_plain.avi")
    create_synthetic_video(video_path, num_frames=10, fps=5.0)

    evidence = extract_video_evidence(
        video_path=video_path,
        reference_date=REF_DATE,
        max_frames=3,
        ocr_text_override_per_frame={0: "NO PARKING IN FRONT OF GATE"}
    )

    # Must contain metadata and neutral OCR summary, NO false CURRENT or OLD
    polarities = [e.polarity for e in evidence]
    assert EvidencePolarity.CURRENT not in polarities
    assert EvidencePolarity.OLD not in polarities
    assert all(p == EvidencePolarity.NEUTRAL for p in polarities)


def test_video_evidence_unreadable_file(tmp_path):
    corrupt_path = str(tmp_path / "corrupt.avi")
    with open(corrupt_path, "wb") as f:
        f.write(b"NOT_A_VALID_VIDEO_STREAM")

    evidence = extract_video_evidence(
        video_path=corrupt_path,
        reference_date=REF_DATE
    )

    assert len(evidence) == 1
    assert evidence[0].source == EvidenceSource.METADATA
    assert evidence[0].polarity == EvidencePolarity.NEUTRAL
    assert "invalid" in evidence[0].finding.lower()
