"""
Drafts a customized cover letter for a job seeker applying to a specific job.

Two paths:
- No OPENAI_API_KEY configured (the default): a template-based draft, built
  from the seeker's profile, the job's details, and their matched/missing
  skills. Fully deterministic, no external calls, works out of the box.
- OPENAI_API_KEY configured: a real LLM call (OpenAI chat completions)
  produces a more natural, genuinely customized draft. Falls back to the
  template automatically if the API call fails for any reason (rate limit,
  bad key, network error) so drafting never hard-fails.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.employer import Employer
from app.models.job import Job
from app.models.job_seeker import JobSeeker
from app.services.matching_service import _get_job_skill_sets, _get_seeker_skill_set, get_missing_skills


def _template_cover_letter(
    job_seeker: JobSeeker,
    job: Job,
    company_name: str,
    matched_skills: list[str],
    missing_required: list[str],
) -> str:
    name = job_seeker.full_name or "the candidate"
    headline = job_seeker.headline or "a motivated professional"
    years = job_seeker.experience_years

    experience_line = (
        f"With {years:g} years of experience as {headline.lower() if headline else 'a professional in this field'}, "
        if years
        else f"As {headline.lower() if headline else 'a professional in this field'}, "
    )

    skills_line = ""
    if matched_skills:
        shown = matched_skills[:5]
        skills_line = f" My background includes hands-on experience with {', '.join(shown)}, which line up directly with what you're looking for."

    growth_line = ""
    if missing_required:
        shown = missing_required[:3]
        growth_line = f" I haven't yet worked directly with {', '.join(shown)}, but I pick up new tools quickly and would welcome the chance to build that experience on the job."

    summary_line = f" {job_seeker.summary}" if job_seeker.summary else ""

    return (
        f"Dear Hiring Manager,\n\n"
        f"I'm writing to apply for the {job.title} position at {company_name}. "
        f"{experience_line}I'm confident I'd be a strong fit for this role.{skills_line}{summary_line}\n\n"
        f"{job.title} at {company_name} stood out to me because of the scope of the work described in the posting, "
        f"and I'm excited about the opportunity to contribute from day one.{growth_line}\n\n"
        f"I'd welcome the chance to discuss how my background fits what you're building. Thank you for your time and consideration.\n\n"
        f"Sincerely,\n{name}"
    )


async def _llm_cover_letter(
    job_seeker: JobSeeker,
    job: Job,
    company_name: str,
    matched_skills: list[str],
    missing_required: list[str],
) -> str | None:
    """Returns None on any failure so the caller can fall back to the template."""
    try:
        from openai import AsyncOpenAI
    except ImportError:
        return None

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        prompt = (
            f"Write a concise, professional cover letter (under 300 words) for this job application.\n\n"
            f"Candidate name: {job_seeker.full_name}\n"
            f"Candidate headline: {job_seeker.headline or 'N/A'}\n"
            f"Candidate summary: {job_seeker.summary or 'N/A'}\n"
            f"Candidate years of experience: {job_seeker.experience_years or 'N/A'}\n"
            f"Skills that match the job: {', '.join(matched_skills) or 'none listed'}\n"
            f"Required skills the candidate does not yet have: {', '.join(missing_required) or 'none'}\n\n"
            f"Job title: {job.title}\n"
            f"Company: {company_name}\n"
            f"Job description: {job.description}\n\n"
            f"Write in first person as the candidate. Be genuine and specific, not generic. "
            f"If there are missing skills, address them briefly and positively rather than ignoring them. "
            f"Do not invent experience the candidate doesn't have."
        )
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return None


async def draft_cover_letter(
    job_seeker: JobSeeker,
    job: Job,
    company_name: str,
    matched_skills: list[str],
    missing_required: list[str],
) -> str:
    if settings.openai_api_key:
        llm_result = await _llm_cover_letter(job_seeker, job, company_name, matched_skills, missing_required)
        if llm_result:
            return llm_result

    return _template_cover_letter(job_seeker, job, company_name, matched_skills, missing_required)


async def draft_cover_letter_for_job(db: AsyncSession, job_seeker: JobSeeker, job: Job) -> str:
    """
    Convenience wrapper: looks up the company name, computes which of the
    job's required skills the seeker already has vs. is missing, and drafts
    the letter. Used by both the /applications/draft-cover-letter endpoint
    and the assistant's "draft an application for job N" intent.
    """
    employer = await db.get(Employer, job.employer_id)
    company_name = employer.company_name if employer else "your company"

    required, _preferred = await _get_job_skill_sets(db, job.id)
    seeker_skills = await _get_seeker_skill_set(db, job_seeker.id)
    seeker_skills_lower = {s.lower() for s in seeker_skills}

    matched = sorted(s for s in required if s.lower() in seeker_skills_lower)
    missing = await get_missing_skills(db, job, job_seeker)

    return await draft_cover_letter(job_seeker, job, company_name, matched, missing["required"])
