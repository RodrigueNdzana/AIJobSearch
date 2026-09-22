import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.job import JobType, JobStatus


class JobCreate(BaseModel):
    title: str
    description: str
    responsibilities: str | None = None
    requirements: str | None = None
    location: str | None = None
    is_remote: bool = False
    job_type: JobType = JobType.full_time
    salary_min: float | None = None
    salary_max: float | None = None
    currency: str = "USD"
    experience_level: str | None = None
    min_experience_years: float | None = None  # explicit; auto-extracted from requirements/description text if left blank
    required_skills: list[str] = []       # skill names, is_required=True
    preferred_skills: list[str] = []      # skill names, is_required=False


class JobUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    responsibilities: str | None = None
    requirements: str | None = None
    location: str | None = None
    is_remote: bool | None = None
    job_type: JobType | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    experience_level: str | None = None
    min_experience_years: float | None = None
    status: JobStatus | None = None


class JobOut(BaseModel):
    id: uuid.UUID
    employer_id: uuid.UUID
    title: str
    description: str
    location: str | None
    is_remote: bool
    job_type: JobType
    salary_min: float | None
    salary_max: float | None
    currency: str | None
    experience_level: str | None
    min_experience_years: float | None = None
    status: JobStatus
    views_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class JobSearchQuery(BaseModel):
    query: str | None = None              # free-text -> semantic search
    location: str | None = None
    job_type: JobType | None = None
    is_remote: bool | None = None
    min_salary: float | None = None
    max_experience_years: float | None = None  # excludes jobs requiring more than this many years
    skills: list[str] = []
    page: int = 1
    page_size: int = 20


class JobSearchResult(JobOut):
    similarity_score: float | None = None  # cosine similarity when semantic search used
    company_name: str | None = None
