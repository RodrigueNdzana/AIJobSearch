import uuid
import enum
from datetime import datetime

from sqlalchemy import Text, Numeric, DateTime, ForeignKey, Enum as SAEnum, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ApplicationStatus(str, enum.Enum):
    pending = "pending"
    reviewed = "reviewed"
    shortlisted = "shortlisted"
    interview = "interview"
    rejected = "rejected"
    hired = "hired"
    withdrawn = "withdrawn"


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("job_id", "job_seeker_id", name="uq_application_job_seeker"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    job_seeker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("job_seekers.id", ondelete="CASCADE"), nullable=False)
    cv_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cvs.id", ondelete="SET NULL"))

    cover_letter: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ApplicationStatus] = mapped_column(SAEnum(ApplicationStatus, name="application_status"), default=ApplicationStatus.pending, nullable=False)
    match_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    employer_notes: Mapped[str | None] = mapped_column(Text)

    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
