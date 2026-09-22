import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.application import ApplicationStatus


class ApplicationCreate(BaseModel):
    job_id: uuid.UUID
    cv_id: uuid.UUID | None = None   # defaults to primary CV if omitted
    cover_letter: str | None = None


class ApplicationStatusUpdate(BaseModel):
    status: ApplicationStatus
    employer_notes: str | None = None


class ApplicationOut(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    job_seeker_id: uuid.UUID
    cv_id: uuid.UUID | None
    cover_letter: str | None
    status: ApplicationStatus
    match_score: float | None
    applied_at: datetime

    class Config:
        from_attributes = True


class CoverLetterDraftRequest(BaseModel):
    job_id: uuid.UUID


class CoverLetterDraftResponse(BaseModel):
    job_id: uuid.UUID
    cover_letter: str
