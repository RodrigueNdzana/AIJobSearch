import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_role
from app.database import get_db
from app.models.employer import Employer
from app.models.job import Job, JobStatus
from app.models.job_seeker import JobSeeker
from app.models.skill import JobSkill, Skill
from app.models.user import User, UserRole
from app.schemas.job import JobCreate, JobOut, JobSearchQuery, JobSearchResult, JobUpdate
from app.services.embedding_service import build_job_text, embed_text
from app.services.matching_service import get_missing_skills, recommend_jobs_for_seeker, run_job_search, semantic_job_search
from app.services.requirement_extraction import extract_min_experience_years

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


async def _get_skill_ids(db: AsyncSession, skill_names: list[str]) -> list[Skill]:
    skills = []
    for name in skill_names:
        result = await db.execute(select(Skill).where(Skill.name == name))
        skill = result.scalar_one_or_none()
        if skill is None:
            skill = Skill(name=name)
            db.add(skill)
            await db.flush()
        skills.append(skill)
    return skills


@router.post("", response_model=JobOut, status_code=status.HTTP_201_CREATED)
async def create_job(
    payload: JobCreate,
    current_user: User = Depends(require_role(UserRole.employer)),
    db: AsyncSession = Depends(get_db),
):
    employer_result = await db.execute(select(Employer).where(Employer.user_id == current_user.id))
    employer = employer_result.scalar_one_or_none()
    if employer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Employer profile not found")

    job = Job(
        employer_id=employer.id,
        title=payload.title,
        description=payload.description,
        responsibilities=payload.responsibilities,
        requirements=payload.requirements,
        location=payload.location,
        is_remote=payload.is_remote,
        job_type=payload.job_type,
        salary_min=payload.salary_min,
        salary_max=payload.salary_max,
        currency=payload.currency,
        experience_level=payload.experience_level,
        min_experience_years=(
            payload.min_experience_years
            if payload.min_experience_years is not None
            else extract_min_experience_years(payload.requirements, payload.description)
        ),
        status=JobStatus.open,
    )

    all_skill_names = payload.required_skills + payload.preferred_skills
    job.embedding = embed_text(build_job_text(payload.title, payload.description, payload.requirements, all_skill_names))

    db.add(job)
    await db.flush()

    for name in payload.required_skills:
        skill = (await _get_skill_ids(db, [name]))[0]
        db.add(JobSkill(job_id=job.id, skill_id=skill.id, is_required=True))
    for name in payload.preferred_skills:
        skill = (await _get_skill_ids(db, [name]))[0]
        db.add(JobSkill(job_id=job.id, skill_id=skill.id, is_required=False))

    await db.commit()
    await db.refresh(job)
    return job


@router.get("/employer/me", response_model=list[JobOut])
async def list_my_jobs(
    current_user: User = Depends(require_role(UserRole.employer)),
    db: AsyncSession = Depends(get_db),
):
    employer_result = await db.execute(select(Employer).where(Employer.user_id == current_user.id))
    employer = employer_result.scalar_one_or_none()
    if employer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Employer profile not found")

    result = await db.execute(
        select(Job).where(Job.employer_id == employer.id).order_by(Job.created_at.desc())
    )
    return result.scalars().all()


@router.get("/recommendations/me", response_model=list[JobSearchResult])
async def get_recommendations(
    current_user: User = Depends(require_role(UserRole.job_seeker)),
    db: AsyncSession = Depends(get_db),
):
    """
    AI-powered job recommendations: ranks open jobs by cosine similarity
    to the seeker's profile_embedding. Call POST /api/job-seekers/me/refresh-embedding
    after profile/skill edits so recommendations reflect the latest profile.
    """
    seeker_result = await db.execute(select(JobSeeker).where(JobSeeker.user_id == current_user.id))
    seeker = seeker_result.scalar_one_or_none()
    if seeker is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job seeker profile not found")

    if seeker.profile_embedding is None:
        return []

    ranked = await recommend_jobs_for_seeker(db, seeker, limit=20)
    results = []
    for job, score in ranked:
        out = JobSearchResult.model_validate(job)
        out.similarity_score = score
        results.append(out)
    return results


@router.post("/search", response_model=list[JobSearchResult])
async def search_jobs(payload: JobSearchQuery, db: AsyncSession = Depends(get_db)):
    """
    Hybrid search: if `query` is present, rank by semantic similarity
    (embedding cosine distance). Otherwise, fall back to filtered listing.
    Structured filters (location, job_type, salary, remote, max experience) always apply.
    """
    page_items = await run_job_search(db, payload)

    results = []
    for job, score in page_items:
        out = JobSearchResult.model_validate(job)
        out.similarity_score = score
        results.append(out)
    return results


@router.get("/{job_id}/missing-skills")
async def missing_skills_for_job(
    job_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.job_seeker)),
    db: AsyncSession = Depends(get_db),
):
    """Skills this job asks for that don't appear on the current seeker's profile, split into required vs preferred."""
    job = await db.get(Job, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    seeker_result = await db.execute(select(JobSeeker).where(JobSeeker.user_id == current_user.id))
    seeker = seeker_result.scalar_one_or_none()
    if seeker is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job seeker profile not found")

    return await get_missing_skills(db, job, seeker)


@router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    job = await db.get(Job, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    job.views_count += 1
    await db.commit()
    await db.refresh(job)
    return job


@router.patch("/{job_id}", response_model=JobOut)
async def update_job(
    job_id: uuid.UUID,
    payload: JobUpdate,
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

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(job, field, value)
    await db.commit()
    await db.refresh(job)
    return job
