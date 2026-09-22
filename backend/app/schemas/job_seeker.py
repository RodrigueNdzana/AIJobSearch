import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class JobSeekerBase(BaseModel):
    full_name: str
    phone: str | None = None
    location: str | None = None
    headline: str | None = None
    summary: str | None = None
    experience_years: float | None = None
    education_level: str | None = None
    portfolio_url: str | None = None
    linkedin_url: str | None = None


class JobSeekerUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    location: str | None = None
    headline: str | None = None
    summary: str | None = None
    experience_years: float | None = None
    education_level: str | None = None
    portfolio_url: str | None = None
    linkedin_url: str | None = None
    is_open_to_work: bool | None = None


class JobSeekerOut(JobSeekerBase):
    id: uuid.UUID
    user_id: uuid.UUID
    is_open_to_work: bool
    created_at: datetime

    class Config:
        from_attributes = True


class SkillIn(BaseModel):
    skill_name: str
    proficiency: str = "intermediate"
    years_used: float | None = None


class SkillOut(BaseModel):
    skill_id: int
    skill_name: str
    proficiency: str
    years_used: float | None = None

    class Config:
        from_attributes = True
