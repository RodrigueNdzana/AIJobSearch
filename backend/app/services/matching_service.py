"""
AI matching logic: semantic search over embeddings plus a hybrid score that
blends embedding similarity with explicit skill overlap. Pure embedding
similarity alone tends to under-weight hard requirements (e.g. "must know
Python"), so match_score combines both signals.
"""

import math

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job, JobStatus
from app.models.job_seeker import JobSeeker
from app.models.skill import JobSeekerSkill, JobSkill, Skill
from app.services.embedding_service import embed_text


async def semantic_job_search(
    db: AsyncSession,
    query_embedding: list[float],
    limit: int = 20,
) -> list[tuple[Job, float]]:
    """
    Returns jobs ranked by cosine similarity to the query embedding, using
    pgvector's <=> operator (cosine distance; lower = more similar).
    similarity_score returned is 1 - distance, so higher = better match.
    """
    stmt = (
        select(Job, (1 - Job.embedding.cosine_distance(query_embedding)).label("similarity"))
        .where(Job.status == "open")
        .order_by(Job.embedding.cosine_distance(query_embedding))
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [(row[0], float(row[1])) for row in result.all()]


async def run_job_search(db: AsyncSession, payload) -> list[tuple[Job, float | None]]:
    """
    Core search logic, shared by the HTTP search endpoint and the assistant
    (so "search again and exclude X" reuses the exact same filtering as a
    normal search). `payload` is a JobSearchQuery (imported lazily below to
    avoid a schemas<->services import cycle). Returns (job, similarity_score)
    pairs, already paginated.
    """
    if payload.query:
        query_embedding = embed_text(payload.query)
        jobs_with_scores = await semantic_job_search(db, query_embedding, limit=payload.page_size * 3)
    else:
        stmt = select(Job).where(Job.status == JobStatus.open)
        result = await db.execute(stmt)
        jobs_with_scores = [(job, None) for job in result.scalars().all()]

    # apply structured filters in Python (fine at moderate scale; push to SQL WHERE for production traffic)
    filtered = []
    for job, score in jobs_with_scores:
        if payload.location and payload.location.lower() not in (job.location or "").lower():
            continue
        if payload.job_type and job.job_type != payload.job_type:
            continue
        if payload.is_remote is not None and job.is_remote != payload.is_remote:
            continue
        if payload.min_salary and (job.salary_max or 0) < payload.min_salary:
            continue
        if payload.max_experience_years is not None and job.min_experience_years is not None:
            if float(job.min_experience_years) > payload.max_experience_years:
                continue
        filtered.append((job, score))

    start = (payload.page - 1) * payload.page_size
    return filtered[start : start + payload.page_size]


async def recommend_jobs_for_seeker(
    db: AsyncSession,
    job_seeker: JobSeeker,
    limit: int = 20,
) -> list[tuple[Job, float]]:
    """Semantic recommendations based on the seeker's profile_embedding."""
    if job_seeker.profile_embedding is None:
        return []
    return await semantic_job_search(db, job_seeker.profile_embedding, limit=limit)


async def _get_job_skill_sets(db: AsyncSession, job_id) -> tuple[set[str], set[str]]:
    """Returns (required_skill_names, preferred_skill_names), lowercased."""
    required_stmt = (
        select(Skill.name)
        .join(JobSkill, JobSkill.skill_id == Skill.id)
        .where(JobSkill.job_id == job_id, JobSkill.is_required == True)  # noqa: E712
    )
    preferred_stmt = (
        select(Skill.name)
        .join(JobSkill, JobSkill.skill_id == Skill.id)
        .where(JobSkill.job_id == job_id, JobSkill.is_required == False)  # noqa: E712
    )
    required = {row[0] for row in (await db.execute(required_stmt)).all()}
    preferred = {row[0] for row in (await db.execute(preferred_stmt)).all()}
    return required, preferred


async def _get_seeker_skill_set(db: AsyncSession, job_seeker_id) -> set[str]:
    stmt = (
        select(Skill.name)
        .join(JobSeekerSkill, JobSeekerSkill.skill_id == Skill.id)
        .where(JobSeekerSkill.job_seeker_id == job_seeker_id)
    )
    return {row[0] for row in (await db.execute(stmt)).all()}


async def get_missing_skills(db: AsyncSession, job: Job, job_seeker: JobSeeker) -> dict[str, list[str]]:
    """
    Returns the skills a job asks for that the seeker's profile doesn't list,
    split into 'required' and 'preferred'. Comparison is case-insensitive but
    results are returned with their original display casing from the
    skills taxonomy.
    """
    required, preferred = await _get_job_skill_sets(db, job.id)
    seeker_skills = await _get_seeker_skill_set(db, job_seeker.id)
    seeker_skills_lower = {s.lower() for s in seeker_skills}

    missing_required = sorted(s for s in required if s.lower() not in seeker_skills_lower)
    missing_preferred = sorted(s for s in preferred if s.lower() not in seeker_skills_lower)

    return {"required": missing_required, "preferred": missing_preferred}


async def compute_match_score(db: AsyncSession, job: Job, job_seeker: JobSeeker) -> float:
    """
    Hybrid 0-100 match score: 60% embedding similarity + 40% required-skill
    overlap. Tune these weights based on what your users respond to.
    """
    similarity = 0.0
    if job.embedding is not None and job_seeker.profile_embedding is not None:
        stmt = select(1 - Job.embedding.cosine_distance(job_seeker.profile_embedding)).where(Job.id == job.id)
        result = await db.execute(stmt)
        raw_similarity = result.scalar()
        similarity = float(raw_similarity) if raw_similarity is not None else 0.0
        if math.isnan(similarity):
            # Cosine similarity of a zero-magnitude embedding is undefined (0/0).
            # Treat it as "no signal" rather than letting NaN propagate into the
            # score and display as "nan%" to the user.
            similarity = 0.0

    required, _preferred = await _get_job_skill_sets(db, job.id)
    required_lower = {s.lower() for s in required}
    seeker_skills_lower = {s.lower() for s in await _get_seeker_skill_set(db, job_seeker.id)}

    skill_overlap = 0.0
    if required_lower:
        skill_overlap = len(required_lower & seeker_skills_lower) / len(required_lower)

    score = (0.6 * similarity + 0.4 * skill_overlap) * 100
    return round(min(max(score, 0.0), 100.0), 2)
