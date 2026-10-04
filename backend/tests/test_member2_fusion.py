"""
test_member2_fusion.py  —  Phase 8 tests
Deterministic; no OCR, Whisper, video files, or network access required.
All inputs are synthetic EvidenceItem objects.
"""

from __future__ import annotations

import pytest

from member2.fusion import (
    ALLOW_CONFIDENCE_THRESHOLD,
    CONFLICT_THRESHOLD,
    DOMINANCE_MARGIN,
    REUSE_MAX_CONTRIBUTION,
    SOURCE_RELIABILITY,
    detect_conflicts,
    fuse_evidence,
)
from member2.schemas import (
    CurrentnessResult,
    CurrentnessVerdict,
    EvidenceItem,
    EvidencePolarity,
    EvidenceSource,
    Member1Context,
    VerificationAction,
)


# ---------------------------------------------------------------------------
# Helpers — synthetic EvidenceItem factories
# ---------------------------------------------------------------------------

def _ev(
    polarity: EvidencePolarity,
    source: EvidenceSource,
    weight: float,
    finding: str = "synthetic finding",
) -> EvidenceItem:
    return EvidenceItem(
        source=source,
        finding=finding,
        polarity=polarity,
        weight=weight,
    )


def _old(source: EvidenceSource = EvidenceSource.TEXT, weight: float = 0.90) -> EvidenceItem:
    return _ev(EvidencePolarity.OLD, source, weight, f"OLD evidence from {source}")


def _current(source: EvidenceSource = EvidenceSource.TEXT, weight: float = 0.90) -> EvidenceItem:
    return _ev(EvidencePolarity.CURRENT, source, weight, f"CURRENT evidence from {source}")


def _neutral(source: EvidenceSource = EvidenceSource.METADATA, weight: float = 0.20) -> EvidenceItem:
    return _ev(EvidencePolarity.NEUTRAL, source, weight, f"NEUTRAL evidence from {source}")


# ---------------------------------------------------------------------------
# 1. No evidence
# ---------------------------------------------------------------------------

class TestNoEvidence:

    def test_empty_list_returns_uncertain(self):
        result = fuse_evidence([])
        assert result.currentness == CurrentnessVerdict.UNCERTAIN

    def test_empty_list_requires_human_verification(self):
        result = fuse_evidence([])
        assert result.action == VerificationAction.HUMAN_VERIFICATION_REQUIRED

    def test_empty_list_has_no_conflicts(self):
        result = fuse_evidence([])
        assert result.conflicts_detected == []

    def test_empty_list_confidence_is_zero(self):
        result = fuse_evidence([])
        assert result.confidence == 0.0

    def test_none_items_handled_safely(self):
        result = fuse_evidence([None, None])  # type: ignore[list-item]
        assert result.currentness == CurrentnessVerdict.UNCERTAIN
        assert result.action == VerificationAction.HUMAN_VERIFICATION_REQUIRED
        assert result.conflicts_detected == []
        assert result.confidence == 0.0

    def test_result_is_currentness_result_type(self):
        result = fuse_evidence([])
        assert isinstance(result, CurrentnessResult)


# ---------------------------------------------------------------------------
# 2. NEUTRAL-only evidence
# ---------------------------------------------------------------------------

class TestNeutralOnly:

    def test_neutral_only_produces_uncertain(self):
        result = fuse_evidence([_neutral(), _neutral(source=EvidenceSource.REFERENCE_CORPUS)])
        assert result.currentness == CurrentnessVerdict.UNCERTAIN

    def test_neutral_only_requires_human_verification(self):
        result = fuse_evidence([_neutral()])
        assert result.action == VerificationAction.HUMAN_VERIFICATION_REQUIRED

    def test_neutral_only_has_no_conflicts(self):
        result = fuse_evidence([_neutral(), _neutral(source=EvidenceSource.REFERENCE_CORPUS)])
        assert result.conflicts_detected == []

    def test_neutral_only_confidence_is_zero(self):
        result = fuse_evidence([_neutral()])
        assert result.confidence == 0.0

    def test_neutral_evidence_preserved_in_result(self):
        items = [_neutral(), _neutral()]
        result = fuse_evidence(items)
        assert len(result.evidence) == 2


# ---------------------------------------------------------------------------
# 3. Strong OLD temporal evidence
# ---------------------------------------------------------------------------

class TestStrongOld:

    def test_strong_old_text_produces_old(self):
        result = fuse_evidence([_old(source=EvidenceSource.TEXT, weight=0.90)])
        assert result.currentness == CurrentnessVerdict.OLD

    def test_strong_old_ocr_produces_old(self):
        result = fuse_evidence([_old(source=EvidenceSource.OCR, weight=0.90)])
        assert result.currentness == CurrentnessVerdict.OLD

    def test_strong_old_allows(self):
        result = fuse_evidence([_old(source=EvidenceSource.TEXT, weight=0.90)])
        assert result.action == VerificationAction.ALLOW
        assert result.confidence >= ALLOW_CONFIDENCE_THRESHOLD

    def test_strong_old_no_current_has_no_conflict(self):
        result = fuse_evidence([_old(source=EvidenceSource.TEXT, weight=0.90)])
        assert result.conflicts_detected == []


# ---------------------------------------------------------------------------
# 4. Strong CURRENT temporal evidence
# ---------------------------------------------------------------------------

class TestStrongCurrent:

    def test_strong_current_text_produces_current(self):
        result = fuse_evidence([_current(source=EvidenceSource.TEXT, weight=0.90)])
        assert result.currentness == CurrentnessVerdict.CURRENT

    def test_strong_current_allows(self):
        result = fuse_evidence([_current(source=EvidenceSource.TEXT, weight=0.90)])
        assert result.action == VerificationAction.ALLOW
        assert result.confidence >= ALLOW_CONFIDENCE_THRESHOLD

    def test_strong_current_no_old_has_no_conflict(self):
        result = fuse_evidence([_current(source=EvidenceSource.TEXT, weight=0.90)])
        assert result.conflicts_detected == []


# ---------------------------------------------------------------------------
# 5. CURRENT + OLD conflict
# ---------------------------------------------------------------------------

class TestConflict:

    def test_bidirectional_strong_evidence_uncertain(self):
        result = fuse_evidence([
            _current(source=EvidenceSource.TEXT, weight=0.90),
            _old(source=EvidenceSource.TEXT, weight=0.90),
        ])
        assert result.currentness == CurrentnessVerdict.UNCERTAIN

    def test_conflict_requires_human_verification(self):
        result = fuse_evidence([
            _current(source=EvidenceSource.TEXT, weight=0.90),
            _old(source=EvidenceSource.TEXT, weight=0.90),
        ])
        assert result.action == VerificationAction.HUMAN_VERIFICATION_REQUIRED

    def test_conflict_is_detected_and_listed(self):
        result = fuse_evidence([
            _current(source=EvidenceSource.TEXT, weight=0.90),
            _old(source=EvidenceSource.TEXT, weight=0.90),
        ])
        assert len(result.conflicts_detected) >= 1

    def test_evidence_preserved_under_conflict(self):
        items = [
            _current(source=EvidenceSource.TEXT, weight=0.90),
            _old(source=EvidenceSource.TEXT, weight=0.90),
        ]
        result = fuse_evidence(items)
        assert len(result.evidence) == 2

    def test_ocr_old_vs_text_current_conflict(self):
        result = fuse_evidence([
            _current(source=EvidenceSource.TEXT, weight=0.85),
            _old(source=EvidenceSource.OCR, weight=0.90),
        ])
        assert result.currentness == CurrentnessVerdict.UNCERTAIN
        assert result.action == VerificationAction.HUMAN_VERIFICATION_REQUIRED


# ---------------------------------------------------------------------------
# 6. Reuse-only evidence
# ---------------------------------------------------------------------------

class TestReuseOnly:

    def test_reuse_only_does_not_produce_current(self):
        result = fuse_evidence([_old(source=EvidenceSource.REUSE, weight=0.80)])
        assert result.currentness != CurrentnessVerdict.CURRENT

    def test_reuse_only_current_evidence_cannot_force_current(self):
        result = fuse_evidence([_current(source=EvidenceSource.REUSE, weight=0.90)])
        assert result.currentness == CurrentnessVerdict.UNCERTAIN

    def test_weak_reuse_stays_cautious(self):
        result = fuse_evidence([_old(source=EvidenceSource.REUSE, weight=0.40)])
        assert result.currentness in (CurrentnessVerdict.UNCERTAIN, CurrentnessVerdict.OLD)

    def test_reuse_contribution_is_capped(self):
        """Many reuse items should NOT produce an extreme score."""
        many_reuse = [_old(source=EvidenceSource.REUSE, weight=0.90) for _ in range(10)]
        result = fuse_evidence(many_reuse)
        assert result.confidence <= 0.93

    def test_reuse_requires_verification_when_weak(self):
        result = fuse_evidence([_old(source=EvidenceSource.REUSE, weight=0.30)])
        assert result.action == VerificationAction.HUMAN_VERIFICATION_REQUIRED

    def test_reuse_alone_requires_human_verification(self):
        result = fuse_evidence([_old(source=EvidenceSource.REUSE, weight=0.90)])
        assert result.action == VerificationAction.HUMAN_VERIFICATION_REQUIRED


# ---------------------------------------------------------------------------
# 7. Reference corpus alone
# ---------------------------------------------------------------------------

class TestReferenceCorpusAlone:

    def test_reference_only_is_cautious(self):
        result = fuse_evidence([
            _old(source=EvidenceSource.REFERENCE_CORPUS, weight=0.70)
        ])
        assert result.currentness == CurrentnessVerdict.UNCERTAIN
        assert result.action == VerificationAction.HUMAN_VERIFICATION_REQUIRED

    def test_reference_only_high_weight_still_cautious(self):
        result = fuse_evidence([
            _old(source=EvidenceSource.REFERENCE_CORPUS, weight=1.0)
        ])
        assert result.currentness == CurrentnessVerdict.UNCERTAIN
        assert result.action == VerificationAction.HUMAN_VERIFICATION_REQUIRED

    def test_reference_only_neutral_is_uncertain(self):
        result = fuse_evidence([
            _neutral(source=EvidenceSource.REFERENCE_CORPUS, weight=0.35)
        ])
        assert result.currentness == CurrentnessVerdict.UNCERTAIN
        assert result.action == VerificationAction.HUMAN_VERIFICATION_REQUIRED
        assert result.conflicts_detected == []


# ---------------------------------------------------------------------------
# 8. Metadata alone
# ---------------------------------------------------------------------------

class TestMetadataAlone:

    def test_metadata_only_old_is_cautious(self):
        result = fuse_evidence([_old(source=EvidenceSource.METADATA, weight=0.80)])
        assert result.currentness in (CurrentnessVerdict.UNCERTAIN, CurrentnessVerdict.OLD)
        assert result.action == VerificationAction.HUMAN_VERIFICATION_REQUIRED

    def test_metadata_alone_does_not_produce_current(self):
        result = fuse_evidence([_neutral(source=EvidenceSource.METADATA)])
        assert result.currentness != CurrentnessVerdict.CURRENT


# ---------------------------------------------------------------------------
# 9. Source deduplication (same source, multiple items)
# ---------------------------------------------------------------------------

class TestSourceDeduplication:

    def test_repeated_ocr_same_polarity_does_not_inflate_score(self):
        """10 OCR OLD items should behave like one (strongest kept)."""
        many_ocr = [_old(source=EvidenceSource.OCR, weight=0.90) for _ in range(10)]
        few_ocr = [_old(source=EvidenceSource.OCR, weight=0.90)]

        result_many = fuse_evidence(many_ocr)
        result_few = fuse_evidence(few_ocr)

        assert result_many.currentness == result_few.currentness
        assert result_many.confidence == result_few.confidence

    def test_dedup_preserves_all_evidence_items(self):
        """Evidence list must NOT be pruned — dedup is scoring-only."""
        items = [_old(source=EvidenceSource.OCR, weight=0.90) for _ in range(5)]
        result = fuse_evidence(items)
        assert len(result.evidence) == 5

    def test_dedup_by_source_and_polarity(self):
        """Deduplication is by (source, polarity): CURRENT and OLD from same source coexist."""
        items = [
            _current(source=EvidenceSource.TEXT, weight=0.80),
            _old(source=EvidenceSource.TEXT, weight=0.80),
        ]
        result = fuse_evidence(items)
        assert result.currentness == CurrentnessVerdict.UNCERTAIN
        assert len(result.conflicts_detected) >= 1


# ---------------------------------------------------------------------------
# 10. Strong OLD + weak CURRENT
# ---------------------------------------------------------------------------

class TestStrongOldWeakCurrent:

    def test_strong_old_wins_over_weak_current(self):
        result = fuse_evidence([
            _old(source=EvidenceSource.TEXT, weight=0.90),
            _current(source=EvidenceSource.REUSE, weight=0.10),
        ])
        assert result.currentness == CurrentnessVerdict.OLD

    def test_no_conflict_if_current_is_below_threshold(self):
        result = fuse_evidence([
            _old(source=EvidenceSource.TEXT, weight=0.90),
            _current(source=EvidenceSource.METADATA, weight=0.05),
        ])
        bidirectional_conflict = any(
            "Directional conflict" in c for c in result.conflicts_detected
        )
        assert not bidirectional_conflict


# ---------------------------------------------------------------------------
# 11. Strong CURRENT + weak OLD
# ---------------------------------------------------------------------------

class TestStrongCurrentWeakOld:

    def test_strong_current_wins_over_weak_old(self):
        result = fuse_evidence([
            _current(source=EvidenceSource.TEXT, weight=0.90),
            _old(source=EvidenceSource.REUSE, weight=0.10),
        ])
        assert result.currentness == CurrentnessVerdict.CURRENT

    def test_strong_current_audio_old_reference_corpus(self):
        result = fuse_evidence([
            _current(source=EvidenceSource.AUDIO, weight=0.85),
            _old(source=EvidenceSource.REFERENCE_CORPUS, weight=0.30),
        ])
        assert result.currentness in (CurrentnessVerdict.CURRENT, CurrentnessVerdict.UNCERTAIN)


# ---------------------------------------------------------------------------
# 12. Confidence always in [0, 1]
# ---------------------------------------------------------------------------

class TestConfidenceRange:

    def test_empty_evidence_confidence_in_range(self):
        result = fuse_evidence([])
        assert 0.0 <= result.confidence <= 1.0

    def test_strong_old_confidence_in_range(self):
        result = fuse_evidence([_old(weight=0.99)])
        assert 0.0 <= result.confidence <= 1.0

    def test_conflict_confidence_in_range(self):
        result = fuse_evidence([_old(), _current()])
        assert 0.0 <= result.confidence <= 1.0

    def test_confidence_never_exceeds_cap(self):
        items = [
            _old(source=EvidenceSource.TEXT, weight=1.0),
            _old(source=EvidenceSource.OCR, weight=1.0),
        ]
        result = fuse_evidence(items)
        assert result.confidence <= 0.93


# ---------------------------------------------------------------------------
# 13. Evidence always preserved in result
# ---------------------------------------------------------------------------

class TestEvidencePreservation:

    def test_all_items_preserved(self):
        items = [_old(), _current(), _neutral()]
        result = fuse_evidence(items)
        assert len(result.evidence) == 3

    def test_neutral_items_preserved_alongside_directional(self):
        items = [_old(), _neutral()]
        result = fuse_evidence(items)
        neutrals = [e for e in result.evidence if e.polarity == EvidencePolarity.NEUTRAL]
        assert len(neutrals) == 1

    def test_contradictory_items_not_discarded(self):
        items = [_old(), _current()]
        result = fuse_evidence(items)
        old_items = [e for e in result.evidence if e.polarity == EvidencePolarity.OLD]
        current_items = [e for e in result.evidence if e.polarity == EvidencePolarity.CURRENT]
        assert len(old_items) >= 1
        assert len(current_items) >= 1


# ---------------------------------------------------------------------------
# 14. Member1Context passes through
# ---------------------------------------------------------------------------

class TestMember1Context:

    def test_context_accepted_without_error(self):
        ctx = Member1Context(is_crisis=True, incident_type="flood")
        result = fuse_evidence([_old()], member1_context=ctx)
        assert isinstance(result, CurrentnessResult)

    def test_context_preserved_in_result(self):
        ctx = Member1Context(is_crisis=True, severity="high")
        result = fuse_evidence([_old()], member1_context=ctx)
        assert result.member1_context is ctx

    def test_none_context_accepted(self):
        result = fuse_evidence([_old()], member1_context=None)
        assert result.member1_context is None


# ---------------------------------------------------------------------------
# 15. Edge cases / safe handling
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_single_neutral_item(self):
        result = fuse_evidence([_neutral()])
        assert result.currentness == CurrentnessVerdict.UNCERTAIN
        assert result.action == VerificationAction.HUMAN_VERIFICATION_REQUIRED

    def test_single_old_item_low_weight(self):
        result = fuse_evidence([_old(source=EvidenceSource.REFERENCE_CORPUS, weight=0.05)])
        assert result.currentness in (CurrentnessVerdict.UNCERTAIN, CurrentnessVerdict.OLD)

    def test_large_mixed_evidence_does_not_crash(self):
        items = (
            [_old(source=EvidenceSource.OCR) for _ in range(5)]
            + [_current(source=EvidenceSource.AUDIO) for _ in range(3)]
            + [_neutral() for _ in range(4)]
        )
        result = fuse_evidence(items)
        assert isinstance(result, CurrentnessResult)
        assert 0.0 <= result.confidence <= 1.0

    def test_verdict_is_valid_enum(self):
        result = fuse_evidence([_old()])
        assert result.currentness in CurrentnessVerdict.__members__.values()

    def test_action_is_valid_enum(self):
        result = fuse_evidence([_old()])
        assert result.action in VerificationAction.__members__.values()


# ---------------------------------------------------------------------------
# 16. Conflict detection function directly
# ---------------------------------------------------------------------------

class TestDetectConflicts:

    def test_no_conflict_when_only_old(self):
        items = [_old(), _old()]
        conflicts = detect_conflicts(items, current_score=0.0, old_score=0.80)
        assert not any("Directional conflict" in c for c in conflicts)

    def test_no_conflict_when_only_current(self):
        items = [_current()]
        conflicts = detect_conflicts(items, current_score=0.80, old_score=0.0)
        assert not any("Directional conflict" in c for c in conflicts)

    def test_conflict_detected_bidirectional(self):
        items = [_current(), _old()]
        conflicts = detect_conflicts(items, current_score=0.70, old_score=0.70)
        assert any("Directional conflict" in c for c in conflicts)

    def test_metadata_vs_text_conflict_detected(self):
        items = [
            _ev(EvidencePolarity.OLD, EvidenceSource.METADATA, 0.70),
            _ev(EvidencePolarity.CURRENT, EvidenceSource.TEXT, 0.80),
        ]
        conflicts = detect_conflicts(items, current_score=0.72, old_score=0.42)
        assert any("Metadata" in c for c in conflicts)

    def test_reuse_vs_strong_current_conflict_detected(self):
        items = [
            _ev(EvidencePolarity.OLD, EvidenceSource.REUSE, 0.80),
            _ev(EvidencePolarity.CURRENT, EvidenceSource.TEXT, 0.85),
        ]
        conflicts = detect_conflicts(items, current_score=0.30, old_score=0.26)
        assert any("reuse" in c.lower() for c in conflicts)
