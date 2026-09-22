import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_role
from app.database import get_db
from app.models.application import Application
from app.models.cv import CV
from app.models.employer import Employer
from app.models.job import Job
from app.models.job_seeker import JobSeeker
from app.models.notification import Notification, NotificationType
from app.models.user import User, UserRole
from app.schemas.application import ApplicationCreate, ApplicationOut, ApplicationStatusUpdate, CoverLetterDraftRequest, CoverLetterDraftResponse
from app.services.cover_letter_service import draft_cover_letter_for_job
from app.services.matching_service import compute_match_score

router = APIRouter(prefix="/api/applications", tags=["applications"])


@router.post("/draft-cover-letter", response_model=CoverLetterDraftResponse)
async def draft_cover_letter_endpoint(
    payload: CoverLetterDraftRequest,
    current_user: User = Depends(require_role(UserRole.job_seeker)),
    db: AsyncSession = Depends(get_db),
):
    """
    Drafts a cover letter for the given job without submitting an
    application — the seeker can review/edit it before applying. Uses a
    template by default, or a real LLM call if OPENAI_API_KEY is configured
    (see app/services/cover_letter_service.py).
    """
    seeker_result = await db.execute(select(JobSeeker).where(JobSeeker.user_id == current_user.id))
    seeker = seeker_result.scalar_one_or_none()
    if seeker is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job seeker profile not found")

    job = await db.get(Job, payload.job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    letter = await draft_cover_letter_for_job(db, seeker, job)
    return CoverLetterDraftResponse(job_id=job.id, cover_letter=letter)


@router.post("", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
async def apply_to_job(
    payload: ApplicationCreate,
    current_user: User = Depends(require_role(UserRole.job_seeker)),
    db: AsyncSession = Depends(get_db),
):
    seeker_result = await db.execute(select(JobSeeker).where(JobSeeker.user_id == current_user.id))
    seeker = seeker_result.scalar_one_or_none()
    if seeker is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job seeker profile not found")

    job = await db.get(Job, payload.job_id)
    if job is None or job.status != "open":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found or not accepting applications")

    existing = await db.execute(
        select(Application).where(Application.job_id == job.id, Application.job_seeker_id == seeker.id)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "You have already applied to this job")

    cv_id = payload.cv_id
    if cv_id is None:
        primary_result = await db.execute(
            select(CV).where(CV.job_seeker_id == seeker.id, CV.is_primary == True)  # noqa: E712
        )
        primary_cv = primary_result.scalar_one_or_none()
        cv_id = primary_cv.id if primary_cv else None

    match_score = await compute_match_score(db, job, seeker)

    application = Application(
        job_id=job.id,
        job_seeker_id=seeker.id,
        cv_id=cv_id,
        cover_letter=payload.cover_letter,
        match_score=match_score,
    )
    db.add(application)

    employer = await db.get(Employer, job.employer_id)
    if employer:
        db.add(Notification(
            user_id=employer.user_id,
            type=NotificationType.new_applicant,
            title="New application received",
            message=f"{seeker.full_name} applied to {job.title}",
            related_entity_type="application",
        ))

    await db.commit()
    await db.refresh(application)
    return application


@router.get("/me", response_model=list[ApplicationOut])
async def my_applications(
    current_user: User = Depends(require_role(UserRole.job_seeker)),
    db: AsyncSession = Depends(get_db),
):
    seeker_result = await db.execute(select(JobSeeker).where(JobSeeker.user_id == current_user.id))
    seeker = seeker_result.scalar_one_or_none()
    if seeker is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job seeker profile not found")

    result = await db.execute(select(Application).where(Application.job_seeker_id == seeker.id))
    return result.scalars().all()


@router.get("/job/{job_id}", response_model=list[ApplicationOut])
async def applicants_for_job(
    job_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.employer)),
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(Job, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    employer_result = await db.execute(select(Employer).where(Employer.user_id == current_user.id))
    employer = employer_result.scalar_one_or_none()
    if employer is None or job.employer_id != employer.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not own this job posting")

    result = await db.execute(
        select(Application).where(Application.job_id == job_id).order_by(Application.match_score.desc())
    )
    return result.scalars().all()


@router.patch("/{application_id}/status", response_model=ApplicationOut)
async def update_application_status(
    application_id: uuid.UUID,
    payload: ApplicationStatusUpdate,
    current_user: User = Depends(require_role(UserRole.employer)),
    db: AsyncSession = Depends(get_db),
):
    application = await db.get(Application, application_id)
    if application is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")

    job = await db.get(Job, application.job_id)
    employer_result = await db.execute(select(Employer).where(Employer.user_id == current_user.id))
    employer = employer_result.scalar_one_or_none()
    if employer is None or job.employer_id != employer.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not own this job posting")

    application.status = payload.status
    if payload.employer_notes is not None:
        application.employer_notes = payload.employer_notes

    seeker = await db.get(JobSeeker, application.job_seeker_id)
    if seeker:
        db.add(Notification(
            user_id=seeker.user_id,
            type=NotificationType.application_status,
            title="Application status updated",
            message=f"Your application for {job.title} is now '{payload.status.value}'",
            related_entity_type="application",
            related_entity_id=application.id,
        ))

    await db.commit()
    await db.refresh(application)
    return application
