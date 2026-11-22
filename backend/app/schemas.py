"""Pydantic contracts for the upload-first EvidenceLens API.

The frontend and backend share these shapes. Status/outcome values are
constrained so the validator can reject anything a model invents.
"""
from typing import Literal, Optional
from pydantic import BaseModel, Field

Uncertainty = Literal["low", "medium", "high"]
DiagnosisStatus = Literal["possible_error", "no_error_observed", "insufficient_evidence"]
ChallengeOutcome = Literal["revise", "uphold", "abstain"]


# ---- Upload -----------------------------------------------------------------
class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str


class VideoUploadResponse(BaseModel):
    video_id: str
    preview_url: str
    duration_s: float
    format: str
    frame_count: int
    has_audio: bool = False
    transcript: list[TranscriptSegment] = Field(default_factory=list)


class EvidenceFrame(BaseModel):
    id: str
    time_s: float
    frame_url: str


# ---- Analyze ----------------------------------------------------------------
class AnalyzeRequest(BaseModel):
    video_id: str
    task_description: str = Field(default="", max_length=1000)
    expected_steps: str = Field(default="", max_length=2000)
    cutoff_s: Optional[float] = Field(default=None, ge=0)


class Claim(BaseModel):
    id: str
    observation: str
    evidence_ids: list[str] = Field(min_length=1)


class Diagnosis(BaseModel):
    diagnosis_id: str
    video_id: str
    mode: Literal["demo", "live"]
    status: DiagnosisStatus
    uncertainty: Uncertainty
    claims: list[Claim] = Field(default_factory=list)  # may be empty when no error
    interpretation: str
    correction: str = ""
    limitations: str = ""
    evidence: list[EvidenceFrame] = Field(default_factory=list)
    used_transcript: list[TranscriptSegment] = Field(default_factory=list)


# ---- Challenge --------------------------------------------------------------
class ChallengeRequest(BaseModel):
    diagnosis_id: str
    claim_id: str
    selected_time_s: float = Field(ge=0)
    user_objection: str = Field(min_length=8, max_length=1200)


class ChallengeResult(BaseModel):
    diagnosis_id: str
    video_id: str
    mode: Literal["demo", "live"]
    outcome: ChallengeOutcome
    changed_claims: list[str] = Field(default_factory=list)
    revised_interpretation: str
    correction: str = ""
    evidence_ids: list[str] = Field(min_length=1)
    uncertainty: Uncertainty
    reason: str
