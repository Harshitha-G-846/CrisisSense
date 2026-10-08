from typing import Literal, Optional

from pydantic import BaseModel, Field


VerificationDecision = Literal[
    "APPROVE",
    "REJECT",
    "NEED_MORE_INFORMATION",
]


class VerificationRequest(BaseModel):
    decision: VerificationDecision
    reason: Optional[str] = Field(
        default=None,
        max_length=1000
    )


class VerificationResponse(BaseModel):
    incident_id: str
    decision: VerificationDecision
    verification_status: str
    reason: Optional[str] = None
    message: str
class FeedbackRequest(BaseModel):
    feedback: str = Field(
        min_length=1,
        max_length=2000
    )


class FeedbackResponse(BaseModel):
    incident_id: str
    feedback: str
    situation_changed: bool
    detected_needs: list[str]
    updated_needs: list[str]
    status: str
    message: str