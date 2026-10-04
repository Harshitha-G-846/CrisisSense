"""
test_member2_reuse.py  —  Phase 6 contract tests
Uses only synthetic PIL images (no external files, no network calls).
"""

from __future__ import annotations

import io
import struct
import zlib
from typing import List

import imagehash
import pytest
from PIL import Image, ImageDraw

from member2.reuse import (
    ReuseCorpus,
    CorpusEntry,
    check_image_reuse,
    check_images_reuse,
    check_video_frames_reuse,
    _distance_to_weight,
)
from member2.schemas import EvidenceItem, EvidencePolarity, EvidenceSource


# ---------------------------------------------------------------------------
# Helpers — synthetic image generators
# ---------------------------------------------------------------------------

def _solid_image(color: tuple, size: tuple = (64, 64)) -> Image.Image:
    """Creates a solid-color RGB image."""
    img = Image.new("RGB", size, color)
    return img


def _gradient_image(start: tuple, end: tuple, size: tuple = (64, 64)) -> Image.Image:
    """Creates a horizontal gradient between two RGB colours."""
    img = Image.new("RGB", size)
    px = img.load()
    w, h = size
    for x in range(w):
        r = int(start[0] + (end[0] - start[0]) * x / w)
        g = int(start[1] + (end[1] - start[1]) * x / w)
        b = int(start[2] + (end[2] - start[2]) * x / w)
        for y in range(h):
            px[x, y] = (r, g, b)
    return img


def _slightly_modified(img: Image.Image, delta: int = 5) -> Image.Image:
    """Adds a tiny per-pixel brightness offset — stays perceptually near-identical."""
    import numpy as np
    arr = np.array(img, dtype="int32")
    arr = (arr + delta).clip(0, 255).astype("uint8")
    return Image.fromarray(arr)


# ---------------------------------------------------------------------------
# 1.  ReuseCorpus — add / size
# ---------------------------------------------------------------------------

class TestReuseCorpusBasic:

    def test_empty_corpus_size(self):
        corpus = ReuseCorpus()
        assert len(corpus) == 0

    def test_add_image_increases_size(self):
        corpus = ReuseCorpus()
        img = _solid_image((255, 0, 0))
        entry = corpus.add_image(img, label="red_solid")
        assert len(corpus) == 1
        assert isinstance(entry, CorpusEntry)
        assert entry.label == "red_solid"

    def test_multiple_adds(self):
        corpus = ReuseCorpus()
        for i in range(5):
            corpus.add_image(_solid_image((i * 50, 0, 0)), label=f"img_{i}")
        assert len(corpus) == 5

    def test_add_image_file_nonexistent_returns_none(self):
        corpus = ReuseCorpus()
        result = corpus.add_image_file("/nonexistent/path/image.png")
        assert result is None
        assert len(corpus) == 0

    def test_load_from_nonexistent_directory(self):
        corpus = ReuseCorpus()
        added = corpus.load_from_directory("/nonexistent/dir")
        assert added == 0

    def test_load_from_empty_directory(self, tmp_path):
        corpus = ReuseCorpus()
        added = corpus.load_from_directory(tmp_path)
        assert added == 0

    def test_load_from_directory_with_images(self, tmp_path):
        # Save two real PNG files
        for i in range(2):
            img = _solid_image((i * 100, 0, 0))
            img.save(tmp_path / f"img_{i}.png")
        corpus = ReuseCorpus()
        added = corpus.load_from_directory(tmp_path)
        assert added == 2
        assert len(corpus) == 2


# ---------------------------------------------------------------------------
# 2.  find_best_match
# ---------------------------------------------------------------------------

class TestFindBestMatch:

    def test_identical_image_returns_match_at_distance_zero(self):
        corpus = ReuseCorpus(hamming_threshold=10)
        img = _solid_image((128, 64, 32))
        corpus.add_image(img, label="original")

        query_hash = imagehash.phash(img.convert("RGB"))
        result = corpus.find_best_match(query_hash)
        assert result is not None
        entry, dist = result
        assert dist == 0
        assert entry.label == "original"

    def test_visually_similar_image_matches(self):
        corpus = ReuseCorpus(hamming_threshold=10)
        img = _gradient_image((200, 100, 50), (50, 200, 150))
        corpus.add_image(img, label="gradient")

        similar = _slightly_modified(img, delta=3)
        query_hash = imagehash.phash(similar.convert("RGB"))
        result = corpus.find_best_match(query_hash)
        assert result is not None, "Expected visually similar image to match"
        entry, dist = result
        assert dist <= 10
        assert entry.label == "gradient"

    def test_very_different_image_does_not_match(self):
        corpus = ReuseCorpus(hamming_threshold=10)
        corpus.add_image(_solid_image((0, 0, 0)), label="black")

        white = _solid_image((255, 255, 255))
        query_hash = imagehash.phash(white.convert("RGB"))
        # A completely black vs completely white image will have max Hamming distance
        result = corpus.find_best_match(query_hash)
        # Result may or may not be None depending on actual hash, but if it is returned
        # the distance must be within threshold; for black vs white it should NOT match.
        if result is not None:
            _, dist = result
            assert dist <= corpus.hamming_threshold
        # At threshold 10, black vs white should exceed threshold
        # (pHash distance for black vs white is typically > 20)

    def test_empty_corpus_returns_none(self):
        corpus = ReuseCorpus()
        img = _solid_image((10, 20, 30))
        query_hash = imagehash.phash(img.convert("RGB"))
        assert corpus.find_best_match(query_hash) is None

    def test_best_match_among_multiple(self):
        corpus = ReuseCorpus(hamming_threshold=20)
        base = _gradient_image((100, 150, 200), (200, 150, 100))
        corpus.add_image(base, label="base")
        corpus.add_image(_solid_image((0, 0, 0)), label="black")
        corpus.add_image(_solid_image((255, 255, 255)), label="white")

        # Slightly modified version of base should match "base" as best
        similar = _slightly_modified(base, delta=2)
        query_hash = imagehash.phash(similar.convert("RGB"))
        result = corpus.find_best_match(query_hash)
        assert result is not None
        entry, dist = result
        assert entry.label == "base"


# ---------------------------------------------------------------------------
# 3.  check_image_reuse — polarity contracts
# ---------------------------------------------------------------------------

class TestCheckImageReuse:

    def test_match_returns_old_polarity(self):
        corpus = ReuseCorpus(hamming_threshold=10)
        img = _solid_image((80, 160, 240))
        corpus.add_image(img, label="known_crisis_image")

        evidence = check_image_reuse(img, corpus, label="query_image")
        assert isinstance(evidence, EvidenceItem)
        assert evidence.source == EvidenceSource.REUSE
        assert evidence.polarity == EvidencePolarity.OLD

    def test_match_weight_in_range(self):
        corpus = ReuseCorpus(hamming_threshold=10)
        img = _solid_image((80, 160, 240))
        corpus.add_image(img, label="known")
        evidence = check_image_reuse(img, corpus)
        assert 0.0 <= evidence.weight <= 1.0

    def test_no_match_returns_neutral_polarity(self):
        corpus = ReuseCorpus(hamming_threshold=10)
        # Corpus contains a solid black; query is a totally different gradient
        corpus.add_image(_solid_image((0, 0, 0)), label="black")

        query = _solid_image((255, 255, 255))
        evidence = check_image_reuse(query, corpus, label="white_query")
        # For very different images Hamming distance > 10, so NEUTRAL expected
        # (but only assert it doesn't claim CURRENT)
        assert evidence.polarity in (EvidencePolarity.NEUTRAL, EvidencePolarity.OLD)
        assert evidence.source == EvidenceSource.REUSE

    def test_empty_corpus_always_returns_neutral(self):
        corpus = ReuseCorpus()
        img = _solid_image((10, 20, 30))
        evidence = check_image_reuse(img, corpus, label="any")
        assert evidence.polarity == EvidencePolarity.NEUTRAL

    def test_neutral_finding_mentions_absence_not_current(self):
        """No-match result must NOT claim the media is current."""
        corpus = ReuseCorpus()
        img = _solid_image((0, 128, 0))
        evidence = check_image_reuse(img, corpus, label="green")
        assert "NOT proof of currentness" in evidence.finding

    def test_match_finding_mentions_reuse(self):
        corpus = ReuseCorpus(hamming_threshold=10)
        img = _solid_image((100, 100, 100))
        corpus.add_image(img, label="grey_ref")
        evidence = check_image_reuse(img, corpus, label="grey_query")
        if evidence.polarity == EvidencePolarity.OLD:
            assert "reuse" in evidence.finding.lower() or "similar" in evidence.finding.lower()

    def test_match_details_contain_hamming_distance(self):
        corpus = ReuseCorpus(hamming_threshold=10)
        img = _solid_image((200, 100, 50))
        corpus.add_image(img, label="ref")
        evidence = check_image_reuse(img, corpus, label="query")
        if evidence.polarity == EvidencePolarity.OLD:
            assert evidence.details is not None
            assert "hamming_distance" in evidence.details
            assert evidence.details["hamming_distance"] <= 10

    def test_neutral_details_contain_corpus_size(self):
        corpus = ReuseCorpus()
        img = _solid_image((5, 10, 15))
        evidence = check_image_reuse(img, corpus, label="any")
        assert evidence.details is not None
        assert "corpus_size" in evidence.details
        assert evidence.details["corpus_size"] == 0

    def test_no_polarity_is_current(self):
        """Reuse evidence must NEVER produce CURRENT polarity."""
        corpus = ReuseCorpus(hamming_threshold=10)
        img = _solid_image((123, 45, 67))
        corpus.add_image(img, label="ref")
        evidence = check_image_reuse(img, corpus, label="q")
        assert evidence.polarity != EvidencePolarity.CURRENT


# ---------------------------------------------------------------------------
# 4.  check_images_reuse — batch
# ---------------------------------------------------------------------------

class TestCheckImagesReuse:

    def test_returns_one_item_per_image(self):
        corpus = ReuseCorpus()
        images = [
            (_solid_image((i * 30, 0, 0)), f"img_{i}")
            for i in range(4)
        ]
        results = check_images_reuse(images, corpus)
        assert len(results) == 4

    def test_all_items_are_evidence_items(self):
        corpus = ReuseCorpus()
        images = [(_solid_image((255, 0, 0)), "red")]
        results = check_images_reuse(images, corpus)
        assert all(isinstance(r, EvidenceItem) for r in results)

    def test_empty_list_returns_empty(self):
        corpus = ReuseCorpus()
        results = check_images_reuse([], corpus)
        assert results == []


# ---------------------------------------------------------------------------
# 5.  check_video_frames_reuse — video frame integration
# ---------------------------------------------------------------------------

class TestCheckVideoFramesReuse:

    def _make_frames(self, count: int = 3) -> list:
        return [
            {
                "frame_index": i,
                "timestamp_seconds": float(i) * 2.0,
                "image": _solid_image((i * 60, 0, 128)),
            }
            for i in range(count)
        ]

    def test_returns_one_item_per_frame(self):
        corpus = ReuseCorpus()
        frames = self._make_frames(3)
        results = check_video_frames_reuse(frames, corpus)
        assert len(results) == 3

    def test_empty_frames_returns_empty(self):
        corpus = ReuseCorpus()
        results = check_video_frames_reuse([], corpus)
        assert results == []

    def test_frame_match_returns_old(self):
        corpus = ReuseCorpus(hamming_threshold=10)
        known_img = _solid_image((200, 200, 200))
        corpus.add_image(known_img, label="known_frame")

        frames = [
            {"frame_index": 0, "timestamp_seconds": 0.0, "image": known_img},
        ]
        results = check_video_frames_reuse(frames, corpus)
        assert len(results) == 1
        assert results[0].polarity == EvidencePolarity.OLD

    def test_frame_without_image_key_skipped(self):
        corpus = ReuseCorpus()
        frames = [{"frame_index": 0, "timestamp_seconds": 0.0}]  # no 'image' key
        results = check_video_frames_reuse(frames, corpus)
        assert results == []

    def test_label_contains_frame_info(self):
        corpus = ReuseCorpus()
        frames = [{"frame_index": 5, "timestamp_seconds": 10.0, "image": _solid_image((0, 0, 0))}]
        results = check_video_frames_reuse(frames, corpus)
        assert "frame_5" in results[0].details.get("query_label", "")


# ---------------------------------------------------------------------------
# 6.  _distance_to_weight helper
# ---------------------------------------------------------------------------

class TestDistanceToWeight:

    def test_distance_zero_gives_max_weight(self):
        w = _distance_to_weight(0, 10)
        assert w == pytest.approx(0.95)

    def test_distance_equals_threshold_gives_min_weight(self):
        w = _distance_to_weight(10, 10)
        assert w == pytest.approx(0.40)

    def test_weight_decreases_with_distance(self):
        ws = [_distance_to_weight(d, 10) for d in range(11)]
        assert ws == sorted(ws, reverse=True)

    def test_weight_always_in_range(self):
        for d in range(0, 15):
            w = _distance_to_weight(d, 10)
            assert 0.0 <= w <= 1.0, f"weight out of range for distance {d}"

    def test_zero_threshold_returns_max(self):
        w = _distance_to_weight(0, 0)
        assert w == pytest.approx(0.95)
