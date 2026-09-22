import uuid
import enum
from datetime import datetime

from sqlalchemy import Text, DateTime, ForeignKey, Enum as SAEnum, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AssistantRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"


class AssistantMessage(Base):
    __tablename__ = "assistant_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_seeker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("job_seekers.id", ondelete="CASCADE"), nullable=False)

    role: Mapped[AssistantRole] = mapped_column(SAEnum(AssistantRole, name="assistant_role"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
