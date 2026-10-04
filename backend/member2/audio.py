"""
audio.py  —  Member 2 / Phase 7
Speech-to-text transcription and temporal evidence extraction from audio files.

Pipeline:
    Audio file
        ↓
    validate_audio_file()          — basic sanity check (exists, non-empty, supported ext)
        ↓
    transcribe_audio()             — speech-to-text via faster-whisper (local, offline)
        ↓
    extract_audio_evidence()       — calls temporal.extract_temporal_evidence() on the
                                     transcript, wraps results as EvidenceSource.AUDIO items
        ↓
    List[EvidenceItem]

CRITICAL RESEARCH DISTINCTION:
    A spoken temporal claim (e.g. "the flood happened in 2021") is evidence about the
    *event* time — NOT proof that the *recording* was made in 2021.
    Evidence weights are therefore kept at a moderate level, not at absolute certainty.

MODEL NOTE:
    faster-whisper requires a local model directory.
    The default is the "tiny" model (≈39 MB) which is suitable for local dev/test.
    The model is loaded lazily on first transcription call.

    To pre-download:
        python -c "from faster_whisper import WhisperModel; WhisperModel('tiny')"

    If no model is available the module degrades gracefully: transcription returns an
    empty transcript and the integration tests are skipped.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from .schemas import EvidenceItem, EvidencePolarity, EvidenceSource
from .temporal import extract_temporal_evidence


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUPPORTED_EXTENSIONS = {
    ".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".opus", ".webm"
}

# Default model size; override via DEFAULT_WHISPER_MODEL env var or argument.
_DEFAULT_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "tiny")

# Weight reduction applied to audio temporal evidence to reflect the inherent
# uncertainty of a spoken claim vs. a documented timestamp.
_AUDIO_WEIGHT_DISCOUNT = 0.10


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_audio_file(path: Union[str, os.PathLike]) -> Tuple[bool, str]:
    """
    Performs lightweight validation of an audio file path.

    Returns:
        (True,  "")          — file looks usable
        (False, reason_str)  — file is not usable, with a human-readable reason
    """
    if not path:
        return False, "No path provided"

    path = str(path)

    if not os.path.exists(path):
        return False, f"File not found: {path}"

    if not os.path.isfile(path):
        return False, f"Path is not a file: {path}"

    if os.path.getsize(path) == 0:
        return False, f"File is empty (0 bytes): {path}"

    ext = os.path.splitext(path)[-1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return False, (
            f"Unsupported audio extension '{ext}'. "
            f"Supported: {sorted(SUPPORTED_EXTENSIONS)}"
        )

    return True, ""


# ---------------------------------------------------------------------------
# Transcription
# ---------------------------------------------------------------------------

class TranscriptSegment:
    """Lightweight container for a single transcription segment."""

    __slots__ = ("text", "start", "end")

    def __init__(self, text: str, start: float, end: float) -> None:
        self.text: str = text.strip()
        self.start: float = start     # segment start (seconds)
        self.end: float = end         # segment end   (seconds)

    def __repr__(self) -> str:
        return f"TranscriptSegment(text={self.text!r}, start={self.start}, end={self.end})"


class TranscriptionResult:
    """Container returned by transcribe_audio()."""

    def __init__(
        self,
        full_text: str,
        segments: List[TranscriptSegment],
        language: Optional[str],
        model_size: str,
        error: Optional[str] = None,
    ) -> None:
        self.full_text: str = full_text
        self.segments: List[TranscriptSegment] = segments
        self.language: Optional[str] = language
        self.model_size: str = model_size
        self.error: Optional[str] = error       # set when transcription failed

    @property
    def succeeded(self) -> bool:
        return self.error is None

    def __repr__(self) -> str:
        return (
            f"TranscriptionResult(language={self.language!r}, "
            f"segments={len(self.segments)}, "
            f"text_length={len(self.full_text)})"
        )


def transcribe_audio(
    audio_path: Union[str, os.PathLike],
    model_size: Optional[str] = None,
    device: str = "cpu",
    compute_type: str = "int8",
) -> TranscriptionResult:
    """
    Transcribes an audio file using faster-whisper (local, offline).

    Args:
        audio_path   : Path to the audio file.
        model_size   : Whisper model size ('tiny', 'base', 'small', ...).
                       Defaults to WHISPER_MODEL_SIZE env var or 'tiny'.
        device       : 'cpu' or 'cuda'.  'cpu' is always safe for local dev.
        compute_type : Quantisation type. 'int8' is fastest on CPU.

    Returns:
        TranscriptionResult — always returns an object; check .succeeded / .error.

    Notes:
        - If faster-whisper is not installed, returns an error TranscriptionResult.
        - If the model files are not cached locally, faster-whisper will attempt to
          download them from HuggingFace Hub on first use.
        - Segment timestamps from faster-whisper are preserved in .segments.
    """
    effective_model_size = model_size or _DEFAULT_MODEL_SIZE

    is_valid, reason = validate_audio_file(audio_path)
    if not is_valid:
        return TranscriptionResult(
            full_text="",
            segments=[],
            language=None,
            model_size=effective_model_size,
            error=reason,
        )

    try:
        from faster_whisper import WhisperModel  # type: ignore[import]
    except ImportError:
        return TranscriptionResult(
            full_text="",
            segments=[],
            language=None,
            model_size=effective_model_size,
            error=(
                "faster-whisper is not installed. "
                "Install it with: pip install faster-whisper"
            ),
        )

    try:
        model = WhisperModel(
            effective_model_size,
            device=device,
            compute_type=compute_type,
        )
        segments_iter, info = model.transcribe(str(audio_path), beam_size=1)

        transcript_segments: List[TranscriptSegment] = []
        for seg in segments_iter:
            transcript_segments.append(
                TranscriptSegment(text=seg.text, start=seg.start, end=seg.end)
            )

        full_text = " ".join(s.text for s in transcript_segments).strip()

        return TranscriptionResult(
            full_text=full_text,
            segments=transcript_segments,
            language=getattr(info, "language", None),
            model_size=effective_model_size,
        )

    except Exception as exc:
        return TranscriptionResult(
            full_text="",
            segments=[],
            language=None,
            model_size=effective_model_size,
            error=f"Transcription failed: {exc}",
        )


# ---------------------------------------------------------------------------
# Evidence extraction
# ---------------------------------------------------------------------------

def extract_audio_evidence(
    audio_path: Union[str, os.PathLike],
    reference_date: Optional[date] = None,
    model_size: Optional[str] = None,
    _transcript_override: Optional[str] = None,   # test/mock injection point
) -> List[EvidenceItem]:
    """
    Full pipeline: validate → transcribe → extract temporal evidence.

    The ``_transcript_override`` parameter allows tests to inject a known
    transcript string without running actual speech recognition. This keeps the
    temporal-evidence logic fully testable without a local Whisper model.

    Returns:
        List[EvidenceItem] with source=EvidenceSource.AUDIO.
        If the audio file is invalid or transcription fails, returns a single
        NEUTRAL EvidenceItem describing the failure.
        If transcription succeeds but the transcript contains no temporal claims,
        returns a single NEUTRAL EvidenceItem.
    """
    if reference_date is None:
        reference_date = datetime.now(timezone.utc).date()

    # --- Validation ---
    if _transcript_override is None:
        is_valid, reason = validate_audio_file(audio_path)
        if not is_valid:
            return [
                EvidenceItem(
                    source=EvidenceSource.AUDIO,
                    finding=f"Audio file could not be processed: {reason}",
                    polarity=EvidencePolarity.NEUTRAL,
                    weight=0.10,
                    details={"error": reason, "audio_path": str(audio_path)},
                )
            ]

    # --- Transcription (or override injection) ---
    if _transcript_override is not None:
        transcript_text = _transcript_override
        transcription_meta: Dict[str, Any] = {
            "source": "override",
            "model_size": "n/a (override)",
        }
    else:
        result = transcribe_audio(audio_path, model_size=model_size)
        if not result.succeeded:
            return [
                EvidenceItem(
                    source=EvidenceSource.AUDIO,
                    finding=f"Transcription failed: {result.error}",
                    polarity=EvidencePolarity.NEUTRAL,
                    weight=0.10,
                    details={
                        "error": result.error,
                        "audio_path": str(audio_path),
                        "model_size": result.model_size,
                    },
                )
            ]
        transcript_text = result.full_text
        transcription_meta = {
            "source": "faster-whisper",
            "model_size": result.model_size,
            "language": result.language,
            "segment_count": len(result.segments),
            "segments": [
                {"text": s.text, "start": s.start, "end": s.end}
                for s in result.segments
            ],
        }

    # --- No speech / empty transcript ---
    if not transcript_text.strip():
        return [
            EvidenceItem(
                source=EvidenceSource.AUDIO,
                finding="Audio transcript is empty — no speech detected or transcription yielded no text",
                polarity=EvidencePolarity.NEUTRAL,
                weight=0.10,
                details={
                    "transcript": "",
                    "audio_path": str(audio_path),
                },
            )
        ]

    # --- Temporal extraction using existing temporal.py ---
    raw_items = extract_temporal_evidence(
        text=transcript_text,
        reference_date=reference_date,
        source=EvidenceSource.TEXT,     # extracted as TEXT first, then re-tagged
    )

    if not raw_items:
        return [
            EvidenceItem(
                source=EvidenceSource.AUDIO,
                finding="Audio transcript contains no detectable temporal claims",
                polarity=EvidencePolarity.NEUTRAL,
                weight=0.15,
                details={
                    "transcript": transcript_text,
                    **(transcription_meta if _transcript_override is None else {}),
                },
            )
        ]

    # --- Re-tag items as AUDIO source + apply moderate weight discount ---
    audio_items: List[EvidenceItem] = []
    for item in raw_items:
        # Spoken claims represent a speaker's assertion, not a verified document timestamp.
        # Apply a small weight discount and re-label the source.
        adjusted_weight = max(0.10, round(item.weight - _AUDIO_WEIGHT_DISCOUNT, 4))

        base_details: Dict[str, Any] = {
            "transcript": transcript_text,
            "temporal_expression": item.details.get("claim") if item.details else None,
        }
        if _transcript_override is None:
            base_details.update(transcription_meta)
        if item.details:
            base_details["temporal_detail"] = item.details

        audio_items.append(
            EvidenceItem(
                source=EvidenceSource.AUDIO,
                finding=f"Spoken temporal claim: {item.finding}",
                polarity=item.polarity,
                weight=adjusted_weight,
                details=base_details,
            )
        )

    return audio_items
