from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_role
from app.database import get_db
from app.models.assistant_message import AssistantMessage, AssistantRole
from app.models.job_seeker import JobSeeker
from app.models.user import User, UserRole
from app.schemas.assistant import AssistantChatRequest, AssistantChatResponse, AssistantMessageOut
from app.services.assistant_service import handle_message

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


async def _get_own_profile(db: AsyncSession, user: User) -> JobSeeker:
    result = await db.execute(select(JobSeeker).where(JobSeeker.user_id == user.id))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job seeker profile not found")
    return profile


@router.post("/chat", response_model=AssistantChatResponse)
async def chat(
    payload: AssistantChatRequest,
    current_user: User = Depends(require_role(UserRole.job_seeker)),
    db: AsyncSession = Depends(get_db),
):
    """
    Conversational entry point. Handles: searching for jobs ("find me five
    Java developer jobs"), ranking the last search results by fit ("which
    of these am I most qualified for"), identifying skill gaps ("what
    skills am I missing"), drafting a cover letter for a job from the last
    search by position ("draft an application for the second job"), and
    refining the last search ("search again and exclude jobs requiring
    more than two years' experience"). Remembers your last search per
    account, so ordinal references ("the second job") resolve correctly
    across turns.
    """
    seeker = await _get_own_profile(db, current_user)

    db.add(AssistantMessage(job_seeker_id=seeker.id, role=AssistantRole.user, content=payload.message))
    await db.commit()

    result = await handle_message(db, seeker, payload.message)

    db.add(AssistantMessage(job_seeker_id=seeker.id, role=AssistantRole.assistant, content=result.reply))
    await db.commit()

    return AssistantChatResponse(
        reply=result.reply,
        jobs=result.jobs,
        missing_skills=result.missing_skills,
        cover_letter=result.cover_letter,
    )


@router.get("/history", response_model=list[AssistantMessageOut])
async def chat_history(
    current_user: User = Depends(require_role(UserRole.job_seeker)),
    db: AsyncSession = Depends(get_db),
):
    seeker = await _get_own_profile(db, current_user)
    result = await db.execute(
        select(AssistantMessage)
        .where(AssistantMessage.job_seeker_id == seeker.id)
        .order_by(AssistantMessage.created_at)
    )
    return result.scalars().all()
