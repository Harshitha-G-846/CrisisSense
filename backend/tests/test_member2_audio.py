"""
test_member2_audio.py  —  Phase 7 tests

Split into two groups:

A. Logic / unit tests  (always run — no model required, use _transcript_override)
B. Integration test    (skipped if faster-whisper model is not locally cached)
"""

from __future__ import annotations

import os
import struct
import wave
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch

import pytest

from member2.audio import (
    SUPPORTED_EXTENSIONS,
    TranscriptSegment,
    TranscriptionResult,
    extract_audio_evidence,
    transcribe_audio,
    validate_audio_file,
)
from member2.schemas import EvidenceItem, EvidencePolarity, EvidenceSource


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_silent_wav(path: Path, duration_seconds: float = 1.0, sample_rate: int = 16000) -> Path:
    """Creates a minimal valid mono WAV file with silence."""
    num_frames = int(sample_rate * duration_seconds)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)   # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * num_frames)
    return path


def _evidence_has_old(items: List[EvidenceItem]) -> bool:
    return any(e.polarity == EvidencePolarity.OLD for e in items)


def _evidence_has_current(items: List[EvidenceItem]) -> bool:
    return any(e.polarity == EvidencePolarity.CURRENT for e in items)


def _evidence_all_audio_source(items: List[EvidenceItem]) -> bool:
    return all(e.source == EvidenceSource.AUDIO for e in items)


# ---------------------------------------------------------------------------
# A.  Logic / unit tests
# ---------------------------------------------------------------------------

class TestValidateAudioFile:

    def test_missing_path_rejected(self):
        ok, reason = validate_audio_file("/nonexistent/file.wav")
        assert not ok
        assert "not found" in reason.lower() or "no path" in reason.lower()

    def test_empty_string_rejected(self):
        ok, reason = validate_audio_file("")
        assert not ok

    def test_directory_rejected(self, tmp_path):
        ok, reason = validate_audio_file(tmp_path)
        assert not ok

    def test_empty_file_rejected(self, tmp_path):
        f = tmp_path / "empty.wav"
        f.write_bytes(b"")
        ok, reason = validate_audio_file(f)
        assert not ok
        assert "empty" in reason.lower()

    def test_unsupported_extension_rejected(self, tmp_path):
        f = tmp_path / "audio.xyz"
        f.write_bytes(b"data")
        ok, reason = validate_audio_file(f)
        assert not ok
        assert "unsupported" in reason.lower() or "xyz" in reason.lower()

    def test_valid_wav_accepted(self, tmp_path):
        wav = _make_silent_wav(tmp_path / "silence.wav")
        ok, reason = validate_audio_file(wav)
        assert ok, f"Expected valid, got: {reason}"
        assert reason == ""

    def test_all_supported_extensions_accepted(self, tmp_path):
        for ext in SUPPORTED_EXTENSIONS:
            f = tmp_path / f"test{ext}"
            f.write_bytes(b"placeholder data")   # non-empty, not checked further
            ok, _ = validate_audio_file(f)
            assert ok, f"Extension {ext} should be supported"


class TestExtractAudioEvidenceWithOverride:
    """
    Uses _transcript_override to bypass actual transcription.
    All temporal logic goes through the real temporal.py.
    """

    def test_old_transcript_produces_old_evidence(self):
        items = extract_audio_evidence(
            audio_path="ignored.wav",
            _transcript_override="The flood happened in 2021.",
        )
        assert len(items) >= 1
        assert _evidence_all_audio_source(items)
        assert _evidence_has_old(items), f"Expected OLD in {items}"

    def test_current_transcript_produces_current_evidence(self):
        items = extract_audio_evidence(
            audio_path="ignored.wav",
            _transcript_override="The fire is happening today.",
        )
        assert len(items) >= 1
        assert _evidence_all_audio_source(items)
        assert _evidence_has_current(items), f"Expected CURRENT in {items}"

    def test_no_temporal_statement_produces_neutral_only(self):
        items = extract_audio_evidence(
            audio_path="ignored.wav",
            _transcript_override="There is a fire nearby. People need help.",
        )
        assert len(items) >= 1
        assert _evidence_all_audio_source(items)
        assert not _evidence_has_old(items), "No OLD expected"
        assert not _evidence_has_current(items), "No CURRENT expected"
        assert all(e.polarity == EvidencePolarity.NEUTRAL for e in items)

    def test_empty_transcript_produces_neutral(self):
        items = extract_audio_evidence(
            audio_path="ignored.wav",
            _transcript_override="",
        )
        assert len(items) == 1
        assert items[0].polarity == EvidencePolarity.NEUTRAL
        assert items[0].source == EvidenceSource.AUDIO

    def test_whitespace_only_transcript_produces_neutral(self):
        items = extract_audio_evidence(
            audio_path="ignored.wav",
            _transcript_override="   \n\t  ",
        )
        assert len(items) == 1
        assert items[0].polarity == EvidencePolarity.NEUTRAL

    def test_transcript_provenance_preserved(self):
        transcript = "The explosion occurred last year."
        items = extract_audio_evidence(
            audio_path="ignored.wav",
            _transcript_override=transcript,
        )
        assert len(items) >= 1
        # Transcript must appear in details
        for item in items:
            if item.polarity != EvidencePolarity.NEUTRAL:
                assert item.details is not None
                assert item.details.get("transcript") == transcript

    def test_audio_evidence_weight_in_valid_range(self):
        items = extract_audio_evidence(
            audio_path="ignored.wav",
            _transcript_override="The flood happened in 2021.",
        )
        for item in items:
            assert 0.0 <= item.weight <= 1.0, f"weight out of range: {item.weight}"

    def test_audio_evidence_weight_discounted(self):
        """
        Audio temporal items should have a lower weight than the raw temporal.py result
        to reflect that they are spoken claims, not verified timestamps.
        """
        from member2.temporal import extract_temporal_evidence
        from member2.schemas import EvidenceSource as ES

        transcript = "The flood happened in 2021."
        raw_items = extract_temporal_evidence(transcript, source=ES.TEXT)
        audio_items = extract_audio_evidence(
            audio_path="ignored.wav",
            _transcript_override=transcript,
        )

        # Filter out the neutral 'no-temporal-claims' fallback if present
        substantive_audio = [i for i in audio_items if i.polarity != EvidencePolarity.NEUTRAL]
        if raw_items and substantive_audio:
            raw_max_weight = max(i.weight for i in raw_items)
            audio_max_weight = max(i.weight for i in substantive_audio)
            assert audio_max_weight < raw_max_weight, (
                f"Audio weight ({audio_max_weight}) should be discounted vs "
                f"raw text weight ({raw_max_weight})"
            )

    def test_evidence_never_claims_recording_date(self):
        """
        Audio evidence must NOT state the recording was made at the claimed time.
        The finding must reflect a spoken claim, not a metadata timestamp.
        """
        items = extract_audio_evidence(
            audio_path="ignored.wav",
            _transcript_override="This happened in 2021.",
        )
        for item in items:
            # finding should reference "spoken" or "claim" — not "recording date"
            assert "recording date" not in item.finding.lower(), (
                f"Finding incorrectly references recording date: {item.finding}"
            )

    def test_no_polarity_is_invalid(self):
        """All returned items must have a valid EvidencePolarity value."""
        items = extract_audio_evidence(
            audio_path="ignored.wav",
            _transcript_override="Flooding ongoing right now, breaking news.",
        )
        valid_polarities = {EvidencePolarity.CURRENT, EvidencePolarity.OLD, EvidencePolarity.NEUTRAL}
        for item in items:
            assert item.polarity in valid_polarities

    def test_all_items_are_evidence_items(self):
        items = extract_audio_evidence(
            audio_path="ignored.wav",
            _transcript_override="Some crisis text.",
        )
        assert all(isinstance(i, EvidenceItem) for i in items)

    def test_breaking_news_produces_current(self):
        items = extract_audio_evidence(
            audio_path="ignored.wav",
            _transcript_override="Breaking news: earthquake happening now.",
        )
        assert _evidence_has_current(items)

    def test_last_year_produces_old(self):
        items = extract_audio_evidence(
            audio_path="ignored.wav",
            _transcript_override="There was a major flood last year.",
        )
        assert _evidence_has_old(items)

    def test_multiple_temporal_claims_produces_multiple_items(self):
        items = extract_audio_evidence(
            audio_path="ignored.wav",
            _transcript_override="The flood in 2021 was followed by fires last year.",
        )
        # At least 2 substantive items
        assert len(items) >= 2


class TestExtractAudioEvidenceInvalidFile:
    """Tests for invalid/missing actual audio files (no transcript override)."""

    def test_missing_file_returns_neutral(self):
        items = extract_audio_evidence(audio_path="/nonexistent/path/audio.wav")
        assert len(items) == 1
        assert items[0].polarity == EvidencePolarity.NEUTRAL
        assert items[0].source == EvidenceSource.AUDIO
        assert "error" in (items[0].details or {})

    def test_unsupported_extension_returns_neutral(self, tmp_path):
        f = tmp_path / "audio.xyz"
        f.write_bytes(b"data")
        items = extract_audio_evidence(audio_path=f)
        assert len(items) == 1
        assert items[0].polarity == EvidencePolarity.NEUTRAL

    def test_empty_file_returns_neutral(self, tmp_path):
        f = tmp_path / "empty.wav"
        f.write_bytes(b"")
        items = extract_audio_evidence(audio_path=f)
        assert len(items) == 1
        assert items[0].polarity == EvidencePolarity.NEUTRAL


class TestTranscribeAudioMocked:
    """Tests for transcribe_audio() using mocking so no model is required."""

    def test_returns_transcription_result(self, tmp_path):
        wav = _make_silent_wav(tmp_path / "s.wav")
        mock_model = MagicMock()
        mock_info = MagicMock()
        mock_info.language = "en"
        mock_seg = MagicMock()
        mock_seg.text = "The flood happened in 2021."
        mock_seg.start = 0.0
        mock_seg.end = 2.5
        mock_model.transcribe.return_value = ([mock_seg], mock_info)

        with patch("member2.audio.WhisperModel", return_value=mock_model, create=True):
            with patch.dict("sys.modules", {"faster_whisper": MagicMock(WhisperModel=MagicMock(return_value=mock_model))}):
                # Import WhisperModel directly into the function scope via patch
                import member2.audio as audio_mod
                orig = getattr(audio_mod, "transcribe_audio")

                # Directly call with the mocked WhisperModel injected
                with patch("member2.audio.WhisperModel", return_value=mock_model):
                    result = audio_mod.transcribe_audio(str(wav))

        assert isinstance(result, TranscriptionResult)

    def test_faster_whisper_not_installed_returns_error(self, tmp_path):
        wav = _make_silent_wav(tmp_path / "s.wav")
        import sys, importlib
        # Temporarily hide faster_whisper from the module
        original = sys.modules.pop("faster_whisper", None)
        try:
            import member2.audio as audio_mod
            # Reload to pick up missing module
            with patch.dict(sys.modules, {"faster_whisper": None}):
                result = audio_mod.transcribe_audio(str(wav))
            assert not result.succeeded
            assert "faster-whisper" in result.error.lower() or "install" in result.error.lower()
        finally:
            if original is not None:
                sys.modules["faster_whisper"] = original

    def test_invalid_file_returns_error_result(self):
        result = transcribe_audio("/nonexistent/audio.wav")
        assert not result.succeeded
        assert result.error is not None
        assert result.full_text == ""
        assert result.segments == []


class TestTranscriptSegmentAndResult:

    def test_transcript_segment_attributes(self):
        seg = TranscriptSegment(text=" hello world ", start=0.5, end=3.2)
        assert seg.text == "hello world"
        assert seg.start == 0.5
        assert seg.end == 3.2

    def test_transcription_result_succeeded(self):
        r = TranscriptionResult(
            full_text="test", segments=[], language="en", model_size="tiny"
        )
        assert r.succeeded is True
        assert r.error is None

    def test_transcription_result_failed(self):
        r = TranscriptionResult(
            full_text="", segments=[], language=None, model_size="tiny",
            error="Some error"
        )
        assert r.succeeded is False
        assert r.error == "Some error"


# ---------------------------------------------------------------------------
# B.  Integration test (skipped if local model unavailable)
# ---------------------------------------------------------------------------

def _local_model_available(model_size: str = "tiny") -> bool:
    """
    Returns True only if faster-whisper is installed AND the model is already
    cached locally (so we don't trigger a download in CI/offline environments).
    """
    try:
        from faster_whisper import WhisperModel  # noqa: F401
    except ImportError:
        return False

    # Check if huggingface hub cache has the model already
    try:
        import huggingface_hub
        # Map whisper model size to its HF repo id
        repo_id = f"Systran/faster-whisper-{model_size}"
        cache_info = huggingface_hub.scan_cache_dir()
        cached_repos = {repo.repo_id for repo in cache_info.repos}
        return repo_id in cached_repos
    except Exception:
        # If we can't check cache, try loading with local_files_only
        try:
            from faster_whisper import WhisperModel
            WhisperModel(model_size, device="cpu", compute_type="int8",
                         local_files_only=True)
            return True
        except Exception:
            return False


@pytest.mark.skipif(
    not _local_model_available("tiny"),
    reason=(
        "No local faster-whisper 'tiny' model found. "
        "Run: python -c \"from faster_whisper import WhisperModel; WhisperModel('tiny')\" "
        "to download it, then re-run this test."
    )
)
class TestAudioIntegration:
    """
    Real transcription test using an actual audio file and the local 'tiny' model.
    Only runs when the model is already cached.
    """

    def test_real_transcription_of_silent_audio(self, tmp_path):
        """Silent audio should produce an empty or near-empty transcript."""
        wav = _make_silent_wav(tmp_path / "silence.wav", duration_seconds=2.0)
        result = transcribe_audio(str(wav), model_size="tiny")
        # Silence should not crash; may produce empty transcript or filler text
        assert isinstance(result, TranscriptionResult)
        # Should not have a hard error
        assert result.error is None or "failed" not in result.error.lower()

    def test_real_transcription_pipeline_does_not_crash(self, tmp_path):
        """
        Full pipeline on a silent file should return a list of EvidenceItems without crashing.
        """
        wav = _make_silent_wav(tmp_path / "silence.wav", duration_seconds=1.0)
        items = extract_audio_evidence(audio_path=str(wav), model_size="tiny")
        assert isinstance(items, list)
        assert all(isinstance(i, EvidenceItem) for i in items)
        assert all(i.source == EvidenceSource.AUDIO for i in items)
