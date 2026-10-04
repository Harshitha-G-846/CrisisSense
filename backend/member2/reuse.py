"""
reuse.py  —  Member 2 / Phase 6
Perceptual-hash-based reused-media detection.

Design contract:
- Accepts PIL Images (from ocr.py or video.py frame samples).
- Computes pHash via imagehash; stores hashes in an in-memory "corpus".
- Returns EvidenceItem objects only; does NOT decide CURRENT / OLD / UNCERTAIN.
- "No match" → NEUTRAL  (absence of a match is NOT proof of currentness).
- "Match found" → OLD polarity (possible reuse signal, not a certainty).
- Hamming distance threshold is configurable (default 10).
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Sequence, Tuple, Union

import imagehash
from PIL import Image

from .schemas import EvidenceItem, EvidencePolarity, EvidenceSource


# ---------------------------------------------------------------------------
# Corpus entry
# ---------------------------------------------------------------------------

@dataclass
class CorpusEntry:
    """A single image hash record stored in the in-memory corpus."""
    label: str                          # human-readable identifier / filename
    phash: imagehash.ImageHash
    added_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# In-memory corpus
# ---------------------------------------------------------------------------

class ReuseCorpus:
    """
    Lightweight in-memory corpus of perceptual hashes.
    Populated at startup from a local directory of known-reused images.
    Can also be extended dynamically during a session.
    """

    def __init__(self, hamming_threshold: int = 10) -> None:
        self._entries: List[CorpusEntry] = []
        self.hamming_threshold = hamming_threshold

    # ------------------------------------------------------------------
    # Population helpers
    # ------------------------------------------------------------------

    def add_image(
        self,
        image: Image.Image,
        label: str,
        metadata: Optional[dict] = None,
    ) -> CorpusEntry:
        """Hash a PIL Image and store it."""
        ph = imagehash.phash(image)
        entry = CorpusEntry(
            label=label,
            phash=ph,
            metadata=metadata or {},
        )
        self._entries.append(entry)
        return entry

    def add_image_file(
        self,
        path: Union[str, os.PathLike],
        label: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[CorpusEntry]:
        """Load an image from disk, hash it, and store it. Returns None on error."""
        path = str(path)
        try:
            img = Image.open(path).convert("RGB")
            return self.add_image(img, label=label or os.path.basename(path), metadata=metadata or {})
        except Exception:
            return None

    def load_from_directory(self, directory: Union[str, os.PathLike]) -> int:
        """
        Walk a directory and hash every loadable image file.
        Returns the number of entries added.
        """
        directory = str(directory)
        if not os.path.isdir(directory):
            return 0

        exts = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tiff"}
        added = 0
        for fname in sorted(os.listdir(directory)):
            ext = os.path.splitext(fname)[-1].lower()
            if ext not in exts:
                continue
            full = os.path.join(directory, fname)
            entry = self.add_image_file(full, label=fname)
            if entry is not None:
                added += 1
        return added

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------

    def find_best_match(
        self, query_hash: imagehash.ImageHash
    ) -> Optional[Tuple[CorpusEntry, int]]:
        """
        Find the corpus entry with the lowest Hamming distance to query_hash.
        Returns (entry, distance) if within threshold, else None.
        """
        best_entry: Optional[CorpusEntry] = None
        best_dist: int = self.hamming_threshold + 1

        for entry in self._entries:
            dist = query_hash - entry.phash
            if dist < best_dist:
                best_dist = dist
                best_entry = entry

        if best_entry is not None and best_dist <= self.hamming_threshold:
            return best_entry, best_dist
        return None

    # ------------------------------------------------------------------
    # Size
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._entries)


# ---------------------------------------------------------------------------
# Single-image evidence extraction
# ---------------------------------------------------------------------------

def check_image_reuse(
    image: Image.Image,
    corpus: ReuseCorpus,
    label: str = "image",
) -> EvidenceItem:
    """
    Compute pHash of image and compare against corpus.

    Returns:
        EvidenceItem with:
          - OLD   polarity  when a match is found within Hamming threshold.
          - NEUTRAL polarity when no match is found (absence ≠ currentness proof).
    """
    try:
        query_hash = imagehash.phash(image.convert("RGB"))
    except Exception as exc:
        return EvidenceItem(
            source=EvidenceSource.REUSE,
            finding=f"Could not compute perceptual hash for {label}: {exc}",
            polarity=EvidencePolarity.NEUTRAL,
            weight=0.10,
            details={"error": str(exc), "label": label},
        )

    match = corpus.find_best_match(query_hash)

    if match is not None:
        matched_entry, distance = match
        return EvidenceItem(
            source=EvidenceSource.REUSE,
            finding=(
                f"Perceptual hash match: '{label}' is visually similar to known corpus "
                f"entry '{matched_entry.label}' (Hamming distance {distance} ≤ {corpus.hamming_threshold}). "
                f"Possible reuse of existing media."
            ),
            polarity=EvidencePolarity.OLD,
            weight=_distance_to_weight(distance, corpus.hamming_threshold),
            details={
                "query_label": label,
                "matched_label": matched_entry.label,
                "hamming_distance": distance,
                "threshold": corpus.hamming_threshold,
                "phash_query": str(query_hash),
                "phash_matched": str(matched_entry.phash),
                "matched_metadata": matched_entry.metadata,
            },
        )

    # No match found → NEUTRAL; do NOT claim media is current
    return EvidenceItem(
        source=EvidenceSource.REUSE,
        finding=(
            f"No perceptual hash match found for '{label}' in the reuse corpus "
            f"({len(corpus)} entries). Absence of match is NOT proof of currentness."
        ),
        polarity=EvidencePolarity.NEUTRAL,
        weight=0.10,
        details={
            "query_label": label,
            "corpus_size": len(corpus),
            "threshold": corpus.hamming_threshold,
            "phash_query": str(query_hash),
        },
    )


# ---------------------------------------------------------------------------
# Multi-image batch helper
# ---------------------------------------------------------------------------

def check_images_reuse(
    images: Sequence[Tuple[Image.Image, str]],
    corpus: ReuseCorpus,
) -> List[EvidenceItem]:
    """
    Run check_image_reuse over a list of (PIL Image, label) pairs.
    Useful for checking multiple video frames in one call.
    """
    return [check_image_reuse(img, corpus, label=lbl) for img, lbl in images]


# ---------------------------------------------------------------------------
# Video-frame integration helper
# ---------------------------------------------------------------------------

def check_video_frames_reuse(
    frames: Sequence[dict],   # dicts from video.sample_video_frames()
    corpus: ReuseCorpus,
) -> List[EvidenceItem]:
    """
    Convenience wrapper that accepts the frame dicts produced by
    video.sample_video_frames() and runs reuse detection on each frame image.

    Each frame dict must contain keys:
        'frame_index'       : int
        'timestamp_seconds' : float
        'image'             : PIL.Image.Image
    """
    items = [
        (f["image"], f"frame_{f['frame_index']} (t={f['timestamp_seconds']}s)")
        for f in frames
        if "image" in f
    ]
    return check_images_reuse(items, corpus)


# ---------------------------------------------------------------------------
# Internal utilities
# ---------------------------------------------------------------------------

def _distance_to_weight(distance: int, threshold: int) -> float:
    """
    Convert Hamming distance into an evidence weight in [0.40, 0.95].
    A smaller distance → higher weight (stronger reuse signal).
    Distance 0  → weight 0.95
    Distance == threshold → weight 0.40
    """
    if threshold <= 0:
        return 0.95
    fraction = max(0.0, min(1.0, distance / threshold))
    return round(0.95 - fraction * 0.55, 4)
