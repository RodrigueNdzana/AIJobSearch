from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_role
from app.database import get_db
from app.models.job_seeker import JobSeeker
from app.models.skill import JobSeekerSkill, Skill
from app.models.user import User, UserRole
from app.schemas.job_seeker import JobSeekerOut, JobSeekerUpdate, SkillIn, SkillOut
from app.services.embedding_service import build_job_seeker_text, embed_text

router = APIRouter(prefix="/api/job-seekers", tags=["job-seekers"])


async def _get_own_profile(db: AsyncSession, user: User) -> JobSeeker:
    result = await db.execute(select(JobSeeker).where(JobSeeker.user_id == user.id))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job seeker profile not found")
    return profile


@router.get("/me", response_model=JobSeekerOut)
async def get_my_profile(
    current_user: User = Depends(require_role(UserRole.job_seeker)),
    db: AsyncSession = Depends(get_db),
):
    return await _get_own_profile(db, current_user)


@router.patch("/me", response_model=JobSeekerOut)
async def update_my_profile(
    payload: JobSeekerUpdate,
    current_user: User = Depends(require_role(UserRole.job_seeker)),
    db: AsyncSession = Depends(get_db),
):
    profile = await _get_own_profile(db, current_user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    await db.commit()
    await db.refresh(profile)
    return profile


@router.get("/me/skills", response_model=list[SkillOut])
async def list_my_skills(
    current_user: User = Depends(require_role(UserRole.job_seeker)),
    db: AsyncSession = Depends(get_db),
):
    profile = await _get_own_profile(db, current_user)
    stmt = (
        select(Skill.id, Skill.name, JobSeekerSkill.proficiency, JobSeekerSkill.years_used)
        .join(JobSeekerSkill, JobSeekerSkill.skill_id == Skill.id)
        .where(JobSeekerSkill.job_seeker_id == profile.id)
    )
    rows = (await db.execute(stmt)).all()
    return [
        SkillOut(skill_id=r[0], skill_name=r[1], proficiency=r[2].value if hasattr(r[2], "value") else r[2], years_used=r[3])
        for r in rows
    ]


@router.post("/me/skills", status_code=status.HTTP_201_CREATED)
async def add_skill(
    payload: SkillIn,
    current_user: User = Depends(require_role(UserRole.job_seeker)),
    db: AsyncSession = Depends(get_db),
):
    profile = await _get_own_profile(db, current_user)

    skill_result = await db.execute(select(Skill).where(Skill.name == payload.skill_name))
    skill = skill_result.scalar_one_or_none()
    if skill is None:
        skill = Skill(name=payload.skill_name)
        db.add(skill)
        await db.flush()

    db.add(JobSeekerSkill(
        job_seeker_id=profile.id,
        skill_id=skill.id,
        proficiency=payload.proficiency,
        years_used=payload.years_used,
    ))
    await db.commit()
    return {"detail": "Skill added"}


@router.delete("/me/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_skill(
    skill_id: int,
    current_user: User = Depends(require_role(UserRole.job_seeker)),
    db: AsyncSession = Depends(get_db),
):
    profile = await _get_own_profile(db, current_user)
    link = await db.get(JobSeekerSkill, (profile.id, skill_id))
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Skill not found on this profile")
    await db.delete(link)
    await db.commit()


@router.post("/me/refresh-embedding")
async def refresh_embedding(
    current_user: User = Depends(require_role(UserRole.job_seeker)),
    db: AsyncSession = Depends(get_db),
):
    """Recompute profile_embedding from the current headline/summary/skills.
    Call this after any profile or skills update so recommendations stay current."""
    profile = await _get_own_profile(db, current_user)

    skills_result = await db.execute(
        select(Skill.name).join(JobSeekerSkill, JobSeekerSkill.skill_id == Skill.id)
        .where(JobSeekerSkill.job_seeker_id == profile.id)
    )
    skill_names = [row[0] for row in skills_result.all()]

    text = build_job_seeker_text(profile.headline, profile.summary, skill_names)
    profile.profile_embedding = embed_text(text)
    await db.commit()
    return {"detail": "Embedding refreshed"}
