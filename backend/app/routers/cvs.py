import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.dependencies import require_role
from app.database import get_db
from app.models.cv import CV
from app.models.job_seeker import JobSeeker
from app.models.user import User, UserRole
from app.schemas.cv import CVAnalysis, CVOut
from app.services.cv_analysis import detect_skills, summarize
from app.services.cv_parser import extract_text
from app.services.embedding_service import embed_text

router = APIRouter(prefix="/api/cvs", tags=["cvs"])

ALLOWED_TYPES = {"pdf", "docx"}


async def _get_own_profile(db: AsyncSession, user: User) -> JobSeeker:
    result = await db.execute(select(JobSeeker).where(JobSeeker.user_id == user.id))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job seeker profile not found")
    return profile


@router.post("/upload", response_model=CVAnalysis, status_code=status.HTTP_201_CREATED)
async def upload_cv(
    file: UploadFile,
    current_user: User = Depends(require_role(UserRole.job_seeker)),
    db: AsyncSession = Depends(get_db),
):
    file_ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if file_ext not in ALLOWED_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"File type must be one of: {', '.join(ALLOWED_TYPES)}")

    file_bytes = await file.read()
    if len(file_bytes) > settings.max_cv_size_mb * 1024 * 1024:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"File exceeds {settings.max_cv_size_mb}MB limit")

    profile = await _get_own_profile(db, current_user)

    # Parse text — malformed files shouldn't 500, just skip AI enrichment
    try:
        parsed_text = extract_text(file_bytes, file_ext)
    except Exception:
        parsed_text = ""

    detected_skills = await detect_skills(db, parsed_text)
    parsed_summary = summarize(parsed_text)
    embedding = embed_text(parsed_text) if parsed_text else None

    # Persist file to local disk (swap for S3/object storage in production)
    os.makedirs(settings.upload_dir, exist_ok=True)
    stored_name = f"{uuid.uuid4()}.{file_ext}"
    file_path = os.path.join(settings.upload_dir, stored_name)
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    # First CV uploaded becomes primary automatically
    existing_count = await db.execute(select(CV).where(CV.job_seeker_id == profile.id))
    is_first_cv = len(existing_count.scalars().all()) == 0

    cv = CV(
        job_seeker_id=profile.id,
        file_name=file.filename,
        file_url=file_path,
        file_type=file_ext,
        parsed_text=parsed_text or None,
        parsed_summary=parsed_summary or None,
        embedding=embedding,
        is_primary=is_first_cv,
    )
    db.add(cv)
    await db.commit()
    await db.refresh(cv)

    return CVAnalysis(
        cv_id=cv.id,
        parsed_summary=cv.parsed_summary,
        detected_skills=detected_skills,
        word_count=len(parsed_text.split()) if parsed_text else 0,
    )


@router.get("/me", response_model=list[CVOut])
async def list_my_cvs(
    current_user: User = Depends(require_role(UserRole.job_seeker)),
    db: AsyncSession = Depends(get_db),
):
    profile = await _get_own_profile(db, current_user)
    result = await db.execute(select(CV).where(CV.job_seeker_id == profile.id))
    cvs = result.scalars().all()
    return [
        CVOut.model_validate(cv, from_attributes=True).model_copy(update={"has_parsed_text": bool(cv.parsed_text)})
        for cv in cvs
    ]


@router.patch("/{cv_id}/set-primary")
async def set_primary_cv(
    cv_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.job_seeker)),
    db: AsyncSession = Depends(get_db),
):
    profile = await _get_own_profile(db, current_user)
    cv = await db.get(CV, cv_id)
    if cv is None or cv.job_seeker_id != profile.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "CV not found")

    await db.execute(update(CV).where(CV.job_seeker_id == profile.id).values(is_primary=False))
    cv.is_primary = True
    await db.commit()
    return {"detail": "Primary CV updated"}


@router.delete("/{cv_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cv(
    cv_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.job_seeker)),
    db: AsyncSession = Depends(get_db),
):
    profile = await _get_own_profile(db, current_user)
    cv = await db.get(CV, cv_id)
    if cv is None or cv.job_seeker_id != profile.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "CV not found")

    if os.path.exists(cv.file_url):
        os.remove(cv.file_url)
    await db.delete(cv)
    await db.commit()
