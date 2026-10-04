import os
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union
from PIL import Image

import cv2

from .schemas import EvidenceItem, EvidencePolarity, EvidenceSource
from .ocr import extract_ocr_evidence, extract_ocr_text


def get_video_metadata(video_path: Union[str, os.PathLike]) -> Dict[str, Any]:
    """
    Safely inspects a local video file and extracts basic structural properties using OpenCV.
    Returns metadata dict.
    """
    default_meta: Dict[str, Any] = {
        "is_valid": False,
        "frame_count": 0,
        "fps": 0.0,
        "width": 0,
        "height": 0,
        "duration_seconds": 0.0
    }

    if not video_path or not isinstance(video_path, (str, os.PathLike)) or not os.path.isfile(video_path):
        return default_meta

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        cap.release()
        return default_meta

    try:
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

        duration = 0.0
        if fps > 0 and frame_count > 0:
            duration = round(frame_count / fps, 2)

        return {
            "is_valid": frame_count > 0 and width > 0 and height > 0,
            "frame_count": frame_count,
            "fps": round(fps, 2),
            "width": width,
            "height": height,
            "duration_seconds": duration
        }
    except Exception:
        return default_meta
    finally:
        cap.release()


def sample_video_frames(
    video_path: Union[str, os.PathLike],
    max_frames: int = 3
) -> List[Dict[str, Any]]:
    """
    Deterministically samples a small subset of representative frames in-memory
    (e.g. beginning, middle, and end) without creating temporary disk files.
    """
    if not video_path or not os.path.isfile(video_path) or max_frames <= 0:
        return []

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        cap.release()
        return []

    sampled: List[Dict[str, Any]] = []
    try:
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)

        if total_frames <= 0:
            return []

        # Determine deterministic sample indices
        if total_frames <= max_frames:
            target_indices = list(range(total_frames))
        elif max_frames == 1:
            target_indices = [total_frames // 2]
        elif max_frames == 2:
            target_indices = [0, total_frames - 1]
        else:
            # e.g., for max_frames=3: [0, total_frames // 2, total_frames - 1]
            step = (total_frames - 1) / (max_frames - 1)
            target_indices = sorted(list({int(round(i * step)) for i in range(max_frames)}))

        for idx in target_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret or frame is None:
                continue

            # Convert OpenCV BGR array to PIL RGB Image
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb_frame)
            ts_sec = round(idx / fps, 2) if fps > 0 else 0.0

            sampled.append({
                "frame_index": idx,
                "timestamp_seconds": ts_sec,
                "image": pil_img
            })

    except Exception:
        pass
    finally:
        cap.release()

    return sampled


def extract_video_evidence(
    video_path: Union[str, os.PathLike],
    reference_date: Optional[date] = None,
    max_frames: int = 3,
    ocr_text_override_per_frame: Optional[Dict[int, str]] = None
) -> List[EvidenceItem]:
    """
    Extracts multimodal currentness evidence from a video file:
    1. Video structure metadata (duration, resolution, frame rate).
    2. Visual OCR temporal evidence from representative in-memory frames.
    """
    if reference_date is None:
        reference_date = datetime.now(timezone.utc).date()

    evidence: List[EvidenceItem] = []
    metadata = get_video_metadata(video_path)

    if not metadata["is_valid"]:
        evidence.append(
            EvidenceItem(
                source=EvidenceSource.METADATA,
                finding="Invalid, missing, or unreadable video file",
                polarity=EvidencePolarity.NEUTRAL,
                weight=0.10,
                details={"video_path": str(video_path)}
            )
        )
        return evidence

    # Emit baseline metadata finding
    evidence.append(
        EvidenceItem(
            source=EvidenceSource.METADATA,
            finding=(
                f"Video properties: {metadata['duration_seconds']:.1f}s duration, "
                f"{metadata['frame_count']} frames at {metadata['fps']:.1f} FPS "
                f"({metadata['width']}x{metadata['height']})"
            ),
            polarity=EvidencePolarity.NEUTRAL,
            weight=0.20,
            details=metadata
        )
    )

    # Sample representative frames
    sampled_frames = sample_video_frames(video_path, max_frames=max_frames)
    ocr_evidence_items: List[EvidenceItem] = []

    for item in sampled_frames:
        frame_idx = item["frame_index"]
        ts_sec = item["timestamp_seconds"]
        pil_img = item["image"]

        # Check for mock/override text if provided
        text_override = None
        if ocr_text_override_per_frame and frame_idx in ocr_text_override_per_frame:
            text_override = ocr_text_override_per_frame[frame_idx]

        frame_ocr_evidence = extract_ocr_evidence(
            image_input=pil_img,
            reference_date=reference_date,
            ocr_text_override=text_override
        )

        for ev in frame_ocr_evidence:
            if ev.polarity in (EvidencePolarity.CURRENT, EvidencePolarity.OLD):
                # Enhance description with frame provenance
                ev.finding = f"Video frame {frame_idx} (t={ts_sec}s): {ev.finding}"
                if ev.details is not None:
                    ev.details["frame_index"] = frame_idx
                    ev.details["timestamp_seconds"] = ts_sec
                ocr_evidence_items.append(ev)

    if ocr_evidence_items:
        evidence.extend(ocr_evidence_items)
    else:
        evidence.append(
            EvidenceItem(
                source=EvidenceSource.OCR,
                finding="No temporal claims detected across sampled video frames",
                polarity=EvidencePolarity.NEUTRAL,
                weight=0.20,
                details={"sampled_frame_count": len(sampled_frames)}
            )
        )

    return evidence
