import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class JobStatus(str, enum.Enum):
    queued = "queued"
    uploading = "uploading"
    separating = "separating"
    analyzing = "analyzing"
    generating = "generating"
    transforming = "transforming"
    exporting = "exporting"
    ready = "ready"
    failed = "failed"
    expired = "expired"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True, index=True
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus), default=JobStatus.queued, index=True
    )
    progress: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(String(500), default="")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    original_filename: Mapped[str] = mapped_column(String(255), default="")
    source_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Análisis
    bpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    key: Mapped[str | None] = mapped_column(String(16), nullable=True)
    time_signature: Mapped[str | None] = mapped_column(String(8), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Transformaciones solicitadas
    target_bpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    transpose_semitones: Mapped[int] = mapped_column(Integer, default=0)
    stem_mode: Mapped[str] = mapped_column(String(32), default="4stems")  # 4stems | 6stems
    count_in_bars: Mapped[int] = mapped_column(Integer, default=1)
    generate_voice_cues: Mapped[bool] = mapped_column(Boolean, default=True)

    # Resultado
    work_dir: Mapped[str | None] = mapped_column(String(500), nullable=True)
    export_zip_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    markers_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="jobs")
