from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CurrentnessVerdict(str, Enum):
    CURRENT = "CURRENT"
    OLD = "OLD"
    UNCERTAIN = "UNCERTAIN"


class VerificationAction(str, Enum):
    ALLOW = "ALLOW"
    HUMAN_VERIFICATION_REQUIRED = "HUMAN_VERIFICATION_REQUIRED"


class EvidencePolarity(str, Enum):
    CURRENT = "CURRENT"
    OLD = "OLD"
    NEUTRAL = "NEUTRAL"


class EvidenceSource(str, Enum):
    TEXT = "text"
    OCR = "ocr"
    AUDIO = "audio"
    METADATA = "metadata"
    VIDEO = "video"
    REUSE = "reuse"
    REFERENCE_CORPUS = "reference_corpus"
    CORROBORATION = "corroboration"


class EvidenceItem(BaseModel):
    source: EvidenceSource
    finding: str = Field(..., min_length=1, description="Description of the observation or finding")
    polarity: EvidencePolarity = Field(
        ...,
        description="Whether this evidence supports CURRENT, OLD, or is NEUTRAL/missing"
    )
    weight: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence or significance weight of this single evidence item"
    )
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional structured metadata for provenance (e.g. extracted date, hash distance)"
    )


class Member1Context(BaseModel):
    is_crisis: Optional[bool] = None
    incident_type: Optional[str] = None
    information_type: Optional[str] = None
    severity: Optional[str] = None
    needs: List[str] = Field(default_factory=list)
    locations: List[Dict[str, Any]] = Field(default_factory=list)


class CurrentnessResult(BaseModel):
    currentness: CurrentnessVerdict
    confidence: float = Field(..., ge=0.0, le=1.0)
    action: VerificationAction
    evidence: List[EvidenceItem] = Field(default_factory=list)
    conflicts_detected: List[str] = Field(
        default_factory=list,
        description="List of detected contradiction descriptions between evidence items"
    )
    member1_context: Optional[Member1Context] = None
