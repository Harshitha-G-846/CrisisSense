import pytest
from pydantic import ValidationError

from member2.schemas import (
    CurrentnessVerdict,
    VerificationAction,
    EvidencePolarity,
    EvidenceSource,
    EvidenceItem,
    Member1Context,
    CurrentnessResult,
)


def test_valid_current_result():
    evidence = [
        EvidenceItem(
            source=EvidenceSource.TEXT,
            finding="Caption indicates 'happening now'",
            polarity=EvidencePolarity.CURRENT,
            weight=0.85,
            details={"claim": "happening now", "direction": "present"},
        ),
        EvidenceItem(
            source=EvidenceSource.METADATA,
            finding="Media creation timestamp matches report date",
            polarity=EvidencePolarity.CURRENT,
            weight=0.90,
        ),
    ]

    result = CurrentnessResult(
        currentness=CurrentnessVerdict.CURRENT,
        confidence=0.88,
        action=VerificationAction.ALLOW,
        evidence=evidence,
        conflicts_detected=[],
        member1_context=Member1Context(
            is_crisis=True,
            incident_type="Fire",
            severity="HIGH",
            needs=["rescue"],
            locations=[{"text": "Whitefield"}],
        ),
    )

    assert result.currentness == CurrentnessVerdict.CURRENT
    assert result.confidence == 0.88
    assert result.action == VerificationAction.ALLOW
    assert len(result.evidence) == 2
    assert result.member1_context.incident_type == "Fire"


def test_valid_old_result():
    evidence = [
        EvidenceItem(
            source=EvidenceSource.OCR,
            finding="Detected date '2021-06-12' in visual frame",
            polarity=EvidencePolarity.OLD,
            weight=0.95,
            details={"extracted_year": 2021},
        ),
        EvidenceItem(
            source=EvidenceSource.REUSE,
            finding="Matched historical disaster media index",
            polarity=EvidencePolarity.OLD,
            weight=0.90,
            details={"match_id": "ref-2021-001", "distance": 2},
        ),
    ]

    result = CurrentnessResult(
        currentness=CurrentnessVerdict.OLD,
        confidence=0.92,
        action=VerificationAction.HUMAN_VERIFICATION_REQUIRED,
        evidence=evidence,
        conflicts_detected=["Caption claims current event but visual OCR indicates 2021"],
    )

    assert result.currentness == CurrentnessVerdict.OLD
    assert result.action == VerificationAction.HUMAN_VERIFICATION_REQUIRED
    assert len(result.conflicts_detected) == 1


def test_valid_uncertain_result_with_neutral_evidence():
    evidence = [
        EvidenceItem(
            source=EvidenceSource.REUSE,
            finding="No reuse match found in local reference index",
            polarity=EvidencePolarity.NEUTRAL,
            weight=0.30,
        ),
        EvidenceItem(
            source=EvidenceSource.TEXT,
            finding="No temporal keywords identified",
            polarity=EvidencePolarity.NEUTRAL,
            weight=0.20,
        ),
    ]

    result = CurrentnessResult(
        currentness=CurrentnessVerdict.UNCERTAIN,
        confidence=0.30,
        action=VerificationAction.HUMAN_VERIFICATION_REQUIRED,
        evidence=evidence,
    )

    assert result.currentness == CurrentnessVerdict.UNCERTAIN
    assert result.confidence == 0.30
    assert result.action == VerificationAction.HUMAN_VERIFICATION_REQUIRED
    assert result.evidence[0].polarity == EvidencePolarity.NEUTRAL


def test_confidence_boundary_and_validation():
    # Valid boundaries
    res_min = CurrentnessResult(
        currentness=CurrentnessVerdict.UNCERTAIN,
        confidence=0.0,
        action=VerificationAction.HUMAN_VERIFICATION_REQUIRED,
    )
    assert res_min.confidence == 0.0

    res_max = CurrentnessResult(
        currentness=CurrentnessVerdict.CURRENT,
        confidence=1.0,
        action=VerificationAction.ALLOW,
    )
    assert res_max.confidence == 1.0

    # Below minimum
    with pytest.raises(ValidationError):
        CurrentnessResult(
            currentness=CurrentnessVerdict.CURRENT,
            confidence=-0.1,
            action=VerificationAction.ALLOW,
        )

    # Above maximum
    with pytest.raises(ValidationError):
        CurrentnessResult(
            currentness=CurrentnessVerdict.CURRENT,
            confidence=1.05,
            action=VerificationAction.ALLOW,
        )


def test_invalid_enum_values():
    # Invalid currentness verdict
    with pytest.raises(ValidationError):
        CurrentnessResult(
            currentness="REAL_TIME",  # Not in enum
            confidence=0.8,
            action=VerificationAction.ALLOW,
        )

    # Invalid action
    with pytest.raises(ValidationError):
        CurrentnessResult(
            currentness=CurrentnessVerdict.CURRENT,
            confidence=0.8,
            action="AUTO_DISPATCH",  # Not in enum
        )

    # Invalid evidence source
    with pytest.raises(ValidationError):
        EvidenceItem(
            source="satellite_radar",  # Not in enum
            finding="Observation",
            polarity=EvidencePolarity.CURRENT,
            weight=0.5,
        )

    # Invalid evidence polarity
    with pytest.raises(ValidationError):
        EvidenceItem(
            source=EvidenceSource.TEXT,
            finding="Observation",
            polarity="POSITIVE",  # Not in enum
            weight=0.5,
        )


def test_malformed_evidence():
    # Weight out of range
    with pytest.raises(ValidationError):
        EvidenceItem(
            source=EvidenceSource.TEXT,
            finding="Finding text",
            polarity=EvidencePolarity.CURRENT,
            weight=1.5,
        )

    # Empty finding
    with pytest.raises(ValidationError):
        EvidenceItem(
            source=EvidenceSource.TEXT,
            finding="",
            polarity=EvidencePolarity.CURRENT,
            weight=0.5,
        )
