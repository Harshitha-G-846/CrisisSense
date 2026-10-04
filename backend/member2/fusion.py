"""
fusion.py  —  Member 2 / Phase 8
Evidence Fusion: deterministic, explainable heuristic currentness assessment.

This module produces the final CurrentnessResult for Member 2.
It does NOT perform ML inference or claim calibrated probabilities.
It applies documented heuristic rules to a list of EvidenceItem objects
and emits a verdict with a heuristic confidence score, verification action,
and detected conflicts for full research traceability.

==============================================================================
DESIGN PRINCIPLES
==============================================================================

1. SOURCE RELIABILITY
   Each EvidenceSource is assigned a reliability scalar in (0, 1].
   Higher reliability = greater weight applied to that source's evidence.
   Values are initial heuristic choices; calibration is deferred to Phase 11.

2. SOURCE DEDUPLICATION
   Deduplication is performed strictly by (source, polarity).
   For scoring, only the single item with the highest effective weight per
   (source, polarity) pair is counted. This prevents repeated evidence from the
   same source/media (e.g. multiple OCR frames from the same video, repeated
   text snippets) from artificially inflating directional scores.
   All original evidence items remain preserved in CurrentnessResult.evidence
   for provenance and explainability.

3. CONFLICT DETECTION
   Conflict exists when there is meaningful CURRENT support AND meaningful OLD
   support simultaneously (effective weights exceeding CONFLICT_THRESHOLD), or
   when cross-source claims contradict (e.g. metadata OLD vs text CURRENT).
   Absence of evidence is NEVER treated as a conflict.

4. REUSE EVIDENCE CAPPING
   Reuse evidence is supporting evidence only. Its directional score contribution
   is hard-capped at REUSE_MAX_CONTRIBUTION. Reuse evidence alone can never
   establish a CURRENT verdict. Uncorroborated reuse evidence always requires
   human verification.

5. REFERENCE CORPUS CONSERVATISM
   A historical CrisisLex corpus event match alone must NOT prove media is OLD.
   Reference corpus evidence alone remains UNCERTAIN and requires human
   verification.

6. VERDICT PRECEDENCE RULES
   a. No directional evidence (empty or neutral-only) -> UNCERTAIN
   b. Material conflict detected -> UNCERTAIN
   c. Solely reference corpus directional evidence -> UNCERTAIN
   d. Solely reuse directional evidence claiming CURRENT -> UNCERTAIN
   e. OLD score exceeds CURRENT score by at least DOMINANCE_MARGIN -> OLD
   f. CURRENT score exceeds OLD score by at least DOMINANCE_MARGIN -> CURRENT
   g. Otherwise -> UNCERTAIN

7. CONFIDENCE
   Heuristic, deterministic, strictly bounded in [0.0, 1.0].
   Empty or neutral-only evidence receives 0.0 confidence.
   It is NOT a statistical probability.

8. ACTION RULES
   ALLOW iff:
     - Verdict is decisively CURRENT or OLD (not UNCERTAIN)
     - Confidence >= ALLOW_CONFIDENCE_THRESHOLD
     - No conflicts detected
     - Supported by primary evidence (not solely indirect sources like REUSE,
       METADATA, or REFERENCE_CORPUS)
   Otherwise -> HUMAN_VERIFICATION_REQUIRED.

==============================================================================
TUNABLE CONSTANTS (heuristic initial values — calibration: Phase 11)
==============================================================================
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from .schemas import (
    CurrentnessResult,
    CurrentnessVerdict,
    EvidenceItem,
    EvidencePolarity,
    EvidenceSource,
    Member1Context,
    VerificationAction,
)

# ---------------------------------------------------------------------------
# Tunable constants
# ---------------------------------------------------------------------------

# Minimum adjusted weight for a polarity side to be "meaningful" in conflict
CONFLICT_THRESHOLD: float = 0.25

# One side must lead by at least this absolute margin to win decisively
DOMINANCE_MARGIN: float = 0.20

# Minimum confidence required to issue ALLOW instead of HUMAN_VERIFICATION_REQUIRED
ALLOW_CONFIDENCE_THRESHOLD: float = 0.55

# Hard cap on the total score contribution from REUSE sources
REUSE_MAX_CONTRIBUTION: float = 0.35

# Source reliability multipliers.
# Heuristic starting points; calibration scheduled for Phase 11:
#   TEXT / OCR       — explicit human-readable temporal claims; high reliability.
#   AUDIO            — spoken claims have ASR acoustic uncertainty; slightly lower.
#   METADATA         — structural, but can be spoofed or re-encoded; moderate.
#   REUSE            — perceptual match is suggestive, not conclusive; moderate.
#   REFERENCE_CORPUS — contextual alignment; cannot directly prove timing alone.
#   VIDEO            — structural visual evidence.
#   CORROBORATION    — secondary cross-check.
SOURCE_RELIABILITY: Dict[EvidenceSource, float] = {
    EvidenceSource.TEXT:             0.90,
    EvidenceSource.OCR:              0.85,
    EvidenceSource.AUDIO:            0.75,
    EvidenceSource.METADATA:         0.60,
    EvidenceSource.REUSE:            0.50,
    EvidenceSource.REFERENCE_CORPUS: 0.50,
    EvidenceSource.VIDEO:            0.60,
    EvidenceSource.CORROBORATION:    0.65,
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _effective_weight(item: EvidenceItem) -> float:
    """item.weight × source reliability multiplier."""
    reliability = SOURCE_RELIABILITY.get(item.source, 0.50)
    return round(item.weight * reliability, 6)


def _deduplicate_by_source(items: List[EvidenceItem]) -> List[EvidenceItem]:
    """
    Deduplicate directional evidence strictly by (source, polarity).

    For each (source, polarity) pair, only the single item with the highest
    effective weight contributes to scoring. This prevents repeated evidence
    from the same source/media (e.g. multiple OCR frames extracted from a single
    video) from dominating directional scoring.

    All original items are preserved in CurrentnessResult.evidence for full
    auditability and provenance.
    """
    best: Dict[Tuple[EvidenceSource, EvidencePolarity], EvidenceItem] = {}
    for item in items:
        key = (item.source, item.polarity)
        existing = best.get(key)
        if existing is None or _effective_weight(item) > _effective_weight(existing):
            best[key] = item
    return list(best.values())


def _score(
    items: List[EvidenceItem],
    polarity: EvidencePolarity,
) -> float:
    """
    Compute the total reliability-adjusted score for the given polarity.

    Steps:
      1. Filter to items matching `polarity`.
      2. Deduplicate by (source, polarity) — keep strongest item per pair.
      3. Cap REUSE contribution to REUSE_MAX_CONTRIBUTION.
      4. Sum effective weights.
    """
    directional = [i for i in items if i.polarity == polarity]
    directional = _deduplicate_by_source(directional)

    total = 0.0
    reuse_total = 0.0

    for item in directional:
        ew = _effective_weight(item)
        if item.source == EvidenceSource.REUSE:
            reuse_total += ew
        else:
            total += ew

    # Enforce reuse cap
    total += min(reuse_total, REUSE_MAX_CONTRIBUTION)
    return round(total, 6)


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------

def detect_conflicts(
    evidence: List[EvidenceItem],
    current_score: float,
    old_score: float,
) -> List[str]:
    """
    Returns a list of human-readable conflict descriptions.

    Conflict is raised when BOTH current_score and old_score exceed
    CONFLICT_THRESHOLD, i.e., there is meaningful evidence on both sides.
    Additional specific cross-source contradictions are also inspected:
      - METADATA OLD vs TEXT/OCR CURRENT
      - REUSE OLD vs strong CURRENT claims (TEXT, OCR, AUDIO)

    Absence of evidence is NEVER treated as a conflict.
    """
    conflicts: List[str] = []

    if current_score >= CONFLICT_THRESHOLD and old_score >= CONFLICT_THRESHOLD:
        conflicts.append(
            f"Directional conflict: CURRENT score {current_score:.3f} and OLD score "
            f"{old_score:.3f} both exceed threshold {CONFLICT_THRESHOLD}. "
            f"Evidence supports both currentness and historical origin."
        )

    # Check for METADATA vs TEXT/OCR conflict at item level
    meta_old = [
        i for i in evidence
        if i.source == EvidenceSource.METADATA
        and i.polarity == EvidencePolarity.OLD
        and _effective_weight(i) >= CONFLICT_THRESHOLD
    ]
    text_current = [
        i for i in evidence
        if i.source in (EvidenceSource.TEXT, EvidenceSource.OCR)
        and i.polarity == EvidencePolarity.CURRENT
        and _effective_weight(i) >= CONFLICT_THRESHOLD
    ]
    if meta_old and text_current:
        conflicts.append(
            "Metadata indicates OLD origin while text/OCR claims CURRENT activity."
        )

    # Meaningful reuse evidence conflicting with strong CURRENT claim
    reuse_old = [
        i for i in evidence
        if i.source == EvidenceSource.REUSE
        and i.polarity == EvidencePolarity.OLD
        and _effective_weight(i) >= CONFLICT_THRESHOLD
    ]
    strong_current = [
        i for i in evidence
        if i.polarity == EvidencePolarity.CURRENT
        and i.source in (EvidenceSource.TEXT, EvidenceSource.OCR, EvidenceSource.AUDIO)
        and i.weight >= 0.70
    ]
    if reuse_old and strong_current:
        conflicts.append(
            "Perceptual reuse match (possible recycled media) conflicts with "
            "strong spoken/written CURRENT claim."
        )

    return conflicts


# ---------------------------------------------------------------------------
# Confidence calculation
# ---------------------------------------------------------------------------

def _calculate_confidence(
    verdict: CurrentnessVerdict,
    current_score: float,
    old_score: float,
    conflicts: List[str],
    has_directional: bool,
) -> float:
    """
    Heuristic, deterministic confidence in [0.0, 1.0].

    - No directional evidence (empty or neutral-only) -> 0.0
    - UNCERTAIN:
        - With conflicts: 0.10 - 0.20 (penalised by conflict count)
        - Without conflicts: 0.30
    - CURRENT / OLD:
        - Winning fraction scaled to [0.40, 0.90] based on dominance.
        - Clamped to 0.93 max to avoid false precision.

    This is an uncalibrated heuristic confidence score, NOT a statistical
    probability. Formal calibration is scheduled for Phase 11.
    """
    if not has_directional:
        return 0.0

    if verdict == CurrentnessVerdict.UNCERTAIN:
        if conflicts:
            penalty = 0.05 * min(len(conflicts), 3)
            return round(max(0.10, 0.25 - penalty), 4)
        return 0.30

    winning_score = current_score if verdict == CurrentnessVerdict.CURRENT else old_score
    total = current_score + old_score

    if total <= 0.0:
        return 0.0

    fraction = winning_score / total
    confidence = 0.40 + fraction * 0.50
    confidence = min(confidence, 0.93)

    return round(confidence, 4)


# ---------------------------------------------------------------------------
# Action determination
# ---------------------------------------------------------------------------

def _determine_action(
    verdict: CurrentnessVerdict,
    confidence: float,
    conflicts: List[str],
    directional_sources: Set[EvidenceSource],
) -> VerificationAction:
    """
    ALLOW iff:
      - Verdict is CURRENT or OLD (not UNCERTAIN)
      - Confidence >= ALLOW_CONFIDENCE_THRESHOLD
      - No conflicts detected
      - Supported by primary evidence (not solely indirect sources like REUSE,
        METADATA, or REFERENCE_CORPUS)

    Everything else -> HUMAN_VERIFICATION_REQUIRED.
    """
    indirect_only = directional_sources.issubset({
        EvidenceSource.REUSE,
        EvidenceSource.REFERENCE_CORPUS,
        EvidenceSource.METADATA,
    })

    if (
        verdict != CurrentnessVerdict.UNCERTAIN
        and confidence >= ALLOW_CONFIDENCE_THRESHOLD
        and not conflicts
        and not indirect_only
    ):
        return VerificationAction.ALLOW

    return VerificationAction.HUMAN_VERIFICATION_REQUIRED


# ---------------------------------------------------------------------------
# Main fusion entry point
# ---------------------------------------------------------------------------

def fuse_evidence(
    evidence: List[EvidenceItem],
    member1_context: Optional[Member1Context] = None,
) -> CurrentnessResult:
    """
    Fuse a list of EvidenceItem objects into a CurrentnessResult.

    Parameters
    ----------
    evidence        : EvidenceItem objects from Member 2 extraction modules.
    member1_context : Optional Member 1 pipeline context (preserved for traceability).

    Returns
    -------
    CurrentnessResult — deterministic, explainable currentness assessment.
    """
    # 1. Guard: empty input
    if not evidence:
        return CurrentnessResult(
            currentness=CurrentnessVerdict.UNCERTAIN,
            confidence=0.0,
            action=VerificationAction.HUMAN_VERIFICATION_REQUIRED,
            evidence=[],
            conflicts_detected=[],
            member1_context=member1_context,
        )

    # Filter out any None items defensively
    valid_evidence: List[EvidenceItem] = [e for e in evidence if e is not None]
    if not valid_evidence:
        return CurrentnessResult(
            currentness=CurrentnessVerdict.UNCERTAIN,
            confidence=0.0,
            action=VerificationAction.HUMAN_VERIFICATION_REQUIRED,
            evidence=[],
            conflicts_detected=[],
            member1_context=member1_context,
        )

    # 2. Score each polarity
    current_score = _score(valid_evidence, EvidencePolarity.CURRENT)
    old_score = _score(valid_evidence, EvidencePolarity.OLD)

    directional_items = [
        i for i in valid_evidence
        if i.polarity in (EvidencePolarity.CURRENT, EvidencePolarity.OLD)
    ]
    has_directional = len(directional_items) > 0 and (current_score > 0.0 or old_score > 0.0)
    directional_sources: Set[EvidenceSource] = {i.source for i in directional_items}

    # 3. Detect conflicts (absence of evidence is never a conflict)
    conflicts = detect_conflicts(valid_evidence, current_score, old_score) if has_directional else []

    # 4. Verdict precedence rules
    if not has_directional:
        # No directional evidence at all (empty or only NEUTRAL items)
        verdict = CurrentnessVerdict.UNCERTAIN

    elif conflicts:
        # Meaningful conflict between CURRENT and OLD evidence
        verdict = CurrentnessVerdict.UNCERTAIN

    elif directional_sources == {EvidenceSource.REFERENCE_CORPUS}:
        # Reference corpus alone cannot prove media is OLD or CURRENT
        verdict = CurrentnessVerdict.UNCERTAIN

    elif directional_sources == {EvidenceSource.REUSE} and current_score > old_score:
        # Reuse evidence alone can NEVER establish CURRENT
        verdict = CurrentnessVerdict.UNCERTAIN

    elif old_score >= CONFLICT_THRESHOLD and (old_score - current_score) >= DOMINANCE_MARGIN:
        # OLD dominates with clear margin
        verdict = CurrentnessVerdict.OLD

    elif current_score >= CONFLICT_THRESHOLD and (current_score - old_score) >= DOMINANCE_MARGIN:
        # CURRENT dominates with clear margin
        verdict = CurrentnessVerdict.CURRENT

    else:
        # Insufficient dominance on either side — uncertain
        verdict = CurrentnessVerdict.UNCERTAIN

    # 5. Confidence calculation
    confidence = _calculate_confidence(verdict, current_score, old_score, conflicts, has_directional)

    # 6. Action determination
    action = _determine_action(verdict, confidence, conflicts, directional_sources)

    return CurrentnessResult(
        currentness=verdict,
        confidence=confidence,
        action=action,
        evidence=valid_evidence,
        conflicts_detected=conflicts,
        member1_context=member1_context,
    )
