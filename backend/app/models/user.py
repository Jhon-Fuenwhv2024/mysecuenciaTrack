import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class MembershipTier(str, enum.Enum):
    free = "free"
    pro = "pro"  # preparado para pagos futuros
    studio = "studio"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120), default="")
    tier: Mapped[MembershipTier] = mapped_column(
        Enum(MembershipTier), default=MembershipTier.free
    )
    songs_used_this_month: Mapped[int] = mapped_column(Integer, default=0)
    billing_cycle_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    jobs = relationship("Job", back_populates="user")
