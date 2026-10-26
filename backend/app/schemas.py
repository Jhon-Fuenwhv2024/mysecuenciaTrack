from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field

from app.models.job import JobStatus
from app.models.user import MembershipTier


class UserCreate(BaseModel):
    email: EmailStr
    display_name: str = ""


class UserOut(BaseModel):
    id: str
    email: EmailStr
    display_name: str
    tier: MembershipTier
    songs_used_this_month: int
    songs_limit: int
    created_at: datetime

    model_config = {"from_attributes": True}


class JobCreateOptions(BaseModel):
    stem_mode: str = Field(default="4stems", pattern="^(4stems|6stems)$")
    target_bpm: float | None = Field(default=None, ge=40, le=240)
    transpose_semitones: int = Field(default=0, ge=-12, le=12)
    count_in_bars: int = Field(default=1, ge=0, le=4)
    generate_voice_cues: bool = True
    user_id: str | None = None


class MarkerUpdate(BaseModel):
    markers: list[dict[str, Any]]


class JobOut(BaseModel):
    id: str
    status: JobStatus
    progress: int
    message: str
    error: str | None = None
    original_filename: str
    bpm: float | None = None
    key: str | None = None
    time_signature: str | None = None
    duration_seconds: float | None = None
    target_bpm: float | None = None
    transpose_semitones: int = 0
    stem_mode: str = "4stems"
    markers: list[dict[str, Any]] | None = None
    analysis: dict[str, Any] | None = None
    stems: list[str] | None = None
    has_export: bool = False
    created_at: datetime
    expires_at: datetime | None = None

    model_config = {"from_attributes": True}


class HealthOut(BaseModel):
    status: str
    app: str
    version: str
    separation_backend: str
    use_gpu: bool
    rubberband: bool
