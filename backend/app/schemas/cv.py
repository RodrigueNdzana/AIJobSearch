import uuid
from datetime import datetime

from pydantic import BaseModel


class CVOut(BaseModel):
    id: uuid.UUID
    job_seeker_id: uuid.UUID
    file_name: str
    file_type: str | None
    is_primary: bool
    uploaded_at: datetime
    has_parsed_text: bool = False

    class Config:
        from_attributes = True


class CVAnalysis(BaseModel):
    """AI-generated analysis of a CV, returned after upload/parse."""
    cv_id: uuid.UUID
    parsed_summary: str | None
    detected_skills: list[str]
    word_count: int
