"""
The conversational job-search assistant. Parses a natural-language message
into one of five intents (search, rank-by-match, missing-skills,
draft-application, refine-search), executes it against the existing
search/matching/cover-letter services, and returns a natural-language reply
plus structured data the frontend can render (job cards, skill lists, etc.).

Intent parsing here is rule-based (regex/keyword matching in text_parsing.py)
rather than an LLM call, so the assistant works with zero API keys
configured — the same "no external dependency required" philosophy as the
rest of the app's AI features. It's scoped to the conversational patterns
job seekers actually use when searching ("find me N X jobs", "which of
these am I most qualified for", "what skills am I missing", "draft an
application for the Nth job", "search again and exclude..."). For more open-
ended conversation, this is the natural place to swap in an LLM call (e.g.
using settings.openai_api_key, already wired up for cover letters).
"""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employer import Employer
from app.models.job import Job
from app.models.job_seeker import JobSeeker
from app.models.search_query import SearchQuery
from app.schemas.job import JobSearchQuery
from app.services.cover_letter_service import draft_cover_letter_for_job
from app.services.matching_service import compute_match_score, get_missing_skills, run_job_search
from app.services.text_parsing import extract_search_query_text, parse_number, parse_ordinal_index

INTENT_SEARCH = "search"
INTENT_RANK = "rank_by_match"
INTENT_MISSING_SKILLS = "missing_skills"
INTENT_DRAFT_APPLICATION = "draft_application"
INTENT_REFINE_SEARCH = "refine_search"

DEFAULT_SEARCH_LIMIT = 10


@dataclass
class AssistantResult:
    reply: str
    jobs: list[dict] = field(default_factory=list)
    missing_skills: dict | None = None
    cover_letter: str | None = None


def classify_intent(message: str) -> str:
    lowered = message.lower()

    if "draft" in lowered and ("application" in lowered or "cover letter" in lowered or "letter" in lowered):
        return INTENT_DRAFT_APPLICATION
    if "missing" in lowered and "skill" in lowered:
        return INTENT_MISSING_SKILLS
    if any(phrase in lowered for phrase in ["most qualified", "which of these", "best fit", "best match", "am i qualified", "rank"]):
        return INTENT_RANK
    if "search again" in lowered or "refine" in lowered or "exclude" in lowered:
        return INTENT_REFINE_SEARCH
    return INTENT_SEARCH


async def _get_last_search(db: AsyncSession, job_seeker_id) -> SearchQuery | None:
    result = await db.execute(
        select(SearchQuery)
        .where(SearchQuery.job_seeker_id == job_seeker_id)
        .order_by(SearchQuery.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _jobs_from_ids(db: AsyncSession, job_ids: list[str]) -> list[Job]:
    if not job_ids:
        return []
    jobs = []
    for jid in job_ids:
        job = await db.get(Job, jid)
        if job is not None:
            jobs.append(job)
    return jobs


async def _company_name(db: AsyncSession, job: Job) -> str:
    employer = await db.get(Employer, job.employer_id)
    return employer.company_name if employer else "Unknown company"


async def _job_to_dict(db: AsyncSession, job: Job, score: float | None = None) -> dict:
    return {
        "id": str(job.id),
        "title": job.title,
        "company_name": await _company_name(db, job),
        "location": job.location,
        "is_remote": job.is_remote,
        "job_type": job.job_type.value if hasattr(job.job_type, "value") else job.job_type,
        "min_experience_years": float(job.min_experience_years) if job.min_experience_years is not None else None,
        "match_score": score,
    }


async def _record_search(db: AsyncSession, job_seeker_id, query_text: str | None, filters: dict, job_ids: list[str]) -> None:
    db.add(SearchQuery(
        job_seeker_id=job_seeker_id,
        query_text=query_text,
        filters=filters,
        result_job_ids=job_ids,
    ))
    await db.commit()


async def handle_search(db: AsyncSession, seeker: JobSeeker, message: str) -> AssistantResult:
    limit = parse_number(message) or DEFAULT_SEARCH_LIMIT
    query_text = extract_search_query_text(message)

    search_payload = JobSearchQuery(query=query_text or None, page=1, page_size=limit)
    page_items = await run_job_search(db, search_payload)

    job_dicts = [await _job_to_dict(db, job, score) for job, score in page_items]
    await _record_search(
        db, seeker.id, query_text,
        {"page_size": limit},
        [j["id"] for j in job_dicts],
    )

    if not job_dicts:
        reply = f"I couldn't find any open jobs matching \"{query_text}\"." if query_text else "I couldn't find any open jobs right now."
    else:
        reply = f"Found {len(job_dicts)} job{'s' if len(job_dicts) != 1 else ''}" + (f" matching \"{query_text}\"" if query_text else "") + "."

    return AssistantResult(reply=reply, jobs=job_dicts)


async def handle_rank(db: AsyncSession, seeker: JobSeeker, message: str) -> AssistantResult:
    last_search = await _get_last_search(db, seeker.id)
    if last_search is None or not last_search.result_job_ids:
        return AssistantResult(reply="I don't have a recent search to rank. Try searching for some jobs first — e.g. \"find me five Java developer jobs\".")

    jobs = await _jobs_from_ids(db, last_search.result_job_ids)
    scored = [(job, await compute_match_score(db, job, seeker)) for job in jobs]
    scored.sort(key=lambda pair: pair[1], reverse=True)

    job_dicts = [await _job_to_dict(db, job, score) for job, score in scored]
    top = job_dicts[0] if job_dicts else None
    reply = (
        f"Ranked by fit: you're the strongest match for \"{top['title']}\" at {top['company_name']} "
        f"({top['match_score']:.0f}% match)." if top else "I don't have any jobs to rank."
    )
    return AssistantResult(reply=reply, jobs=job_dicts)


async def handle_missing_skills(db: AsyncSession, seeker: JobSeeker, message: str) -> AssistantResult:
    last_search = await _get_last_search(db, seeker.id)
    if last_search is None or not last_search.result_job_ids:
        return AssistantResult(reply="I don't have a recent search to check. Try searching for some jobs first.")

    ordinal = parse_ordinal_index(message)
    job_ids = last_search.result_job_ids
    index = ordinal if ordinal is not None and 0 <= ordinal < len(job_ids) else 0
    job = await db.get(Job, job_ids[index])
    if job is None:
        return AssistantResult(reply="I couldn't find that job anymore — it may have been closed. Try searching again.")

    missing = await get_missing_skills(db, job, seeker)
    if not missing["required"] and not missing["preferred"]:
        reply = f"You've got everything listed for \"{job.title}\" — no missing skills."
    else:
        parts = []
        if missing["required"]:
            parts.append(f"required: {', '.join(missing['required'])}")
        if missing["preferred"]:
            parts.append(f"preferred: {', '.join(missing['preferred'])}")
        reply = f"For \"{job.title}\", you're missing — {'; '.join(parts)}."

    return AssistantResult(reply=reply, missing_skills=missing, jobs=[await _job_to_dict(db, job)])


async def handle_draft_application(db: AsyncSession, seeker: JobSeeker, message: str) -> AssistantResult:
    last_search = await _get_last_search(db, seeker.id)
    if last_search is None or not last_search.result_job_ids:
        return AssistantResult(reply="I don't have a recent search to draft from. Try searching for some jobs first, then ask me to draft an application for one of them.")

    ordinal = parse_ordinal_index(message)
    job_ids = last_search.result_job_ids
    index = ordinal if ordinal is not None else 0
    if not (0 <= index < len(job_ids)):
        return AssistantResult(reply=f"I only have {len(job_ids)} job(s) from your last search — which one did you mean?")

    job = await db.get(Job, job_ids[index])
    if job is None:
        return AssistantResult(reply="I couldn't find that job anymore — it may have been closed. Try searching again.")

    letter = await draft_cover_letter_for_job(db, seeker, job)
    reply = f"Here's a draft cover letter for \"{job.title}\":"
    return AssistantResult(reply=reply, cover_letter=letter, jobs=[await _job_to_dict(db, job)])


async def handle_refine_search(db: AsyncSession, seeker: JobSeeker, message: str) -> AssistantResult:
    last_search = await _get_last_search(db, seeker.id)
    query_text = last_search.query_text if last_search else extract_search_query_text(message)
    prior_filters = dict(last_search.filters or {}) if last_search else {}

    max_years = parse_number(message) if "year" in message.lower() else None

    limit = prior_filters.get("page_size", DEFAULT_SEARCH_LIMIT)
    search_payload = JobSearchQuery(
        query=query_text or None,
        page=1,
        page_size=limit,
        max_experience_years=float(max_years) if max_years is not None else None,
    )
    page_items = await run_job_search(db, search_payload)
    job_dicts = [await _job_to_dict(db, job, score) for job, score in page_items]

    new_filters = dict(prior_filters)
    if max_years is not None:
        new_filters["max_experience_years"] = max_years
    await _record_search(db, seeker.id, query_text, new_filters, [j["id"] for j in job_dicts])

    if max_years is not None:
        reply = f"Searched again, excluding jobs requiring more than {max_years} years' experience. Found {len(job_dicts)} job{'s' if len(job_dicts) != 1 else ''}."
    else:
        reply = f"Searched again. Found {len(job_dicts)} job{'s' if len(job_dicts) != 1 else ''}."

    return AssistantResult(reply=reply, jobs=job_dicts)


_HANDLERS = {
    INTENT_SEARCH: handle_search,
    INTENT_RANK: handle_rank,
    INTENT_MISSING_SKILLS: handle_missing_skills,
    INTENT_DRAFT_APPLICATION: handle_draft_application,
    INTENT_REFINE_SEARCH: handle_refine_search,
}


async def handle_message(db: AsyncSession, seeker: JobSeeker, message: str) -> AssistantResult:
    intent = classify_intent(message)
    handler = _HANDLERS[intent]
    return await handler(db, seeker, message)
