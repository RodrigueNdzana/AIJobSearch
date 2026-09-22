import uuid
from datetime import datetime

from pydantic import BaseModel


class EmployerBase(BaseModel):
    company_name: str
    company_description: str | None = None
    industry: str | None = None
    company_size: str | None = None
    website_url: str | None = None
    logo_url: str | None = None
    location: str | None = None


class EmployerUpdate(BaseModel):
    company_name: str | None = None
    company_description: str | None = None
    industry: str | None = None
    company_size: str | None = None
    website_url: str | None = None
    logo_url: str | None = None
    location: str | None = None


class EmployerOut(EmployerBase):
    id: uuid.UUID
    user_id: uuid.UUID
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True
