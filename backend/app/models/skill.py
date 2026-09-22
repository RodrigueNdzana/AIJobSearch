import uuid
import enum

from sqlalchemy import String, Integer, Boolean, Numeric, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProficiencyLevel(str, enum.Enum):
    beginner = "beginner"
    intermediate = "intermediate"
    advanced = "advanced"
    expert = "expert"


proficiency_level_type = SAEnum(ProficiencyLevel, name="proficiency_level")


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100))


class JobSeekerSkill(Base):
    __tablename__ = "job_seeker_skills"

    job_seeker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("job_seekers.id", ondelete="CASCADE"), primary_key=True)
    skill_id: Mapped[int] = mapped_column(Integer, ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True)
    proficiency: Mapped[ProficiencyLevel] = mapped_column(proficiency_level_type, default=ProficiencyLevel.intermediate, nullable=False)
    years_used: Mapped[float | None] = mapped_column(Numeric(4, 1))


class JobSkill(Base):
    __tablename__ = "job_skills"

    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True)
    skill_id: Mapped[int] = mapped_column(Integer, ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    min_proficiency: Mapped[ProficiencyLevel] = mapped_column(proficiency_level_type, default=ProficiencyLevel.intermediate, nullable=False)
