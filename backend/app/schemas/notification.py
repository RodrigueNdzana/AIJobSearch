import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.notification import NotificationType


class NotificationOut(BaseModel):
    id: uuid.UUID
    type: NotificationType
    title: str
    message: str
    related_entity_type: str | None
    related_entity_id: uuid.UUID | None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True
