import uuid
from datetime import datetime

from pydantic import BaseModel


class AssistantChatRequest(BaseModel):
    message: str


class AssistantJobResult(BaseModel):
    id: str
    title: str
    company_name: str
    location: str | None = None
    is_remote: bool
    job_type: str
    min_experience_years: float | None = None
    match_score: float | None = None


class AssistantChatResponse(BaseModel):
    reply: str
    jobs: list[AssistantJobResult] = []
    missing_skills: dict[str, list[str]] | None = None
    cover_letter: str | None = None


class AssistantMessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True
