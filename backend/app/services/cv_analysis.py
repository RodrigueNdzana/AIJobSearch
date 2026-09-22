"""
Analyzes parsed CV text: detects known skills by matching against the skills
taxonomy, and produces a short summary. The summary here is a simple
heuristic (first N sentences) — swap _summarize() for a call to an LLM
(OpenAI/Claude) for a genuinely abstractive summary in production.
"""

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import Skill


async def detect_skills(db: AsyncSession, text: str) -> list[str]:
    """Match known skills (from the skills taxonomy) against CV text by substring."""
    if not text:
        return []
    result = await db.execute(select(Skill.name))
    all_skills = [row[0] for row in result.all()]

    text_lower = text.lower()
    found = [s for s in all_skills if re.search(rf"\b{re.escape(s.lower())}\b", text_lower)]
    return found


def summarize(text: str, max_sentences: int = 3) -> str:
    """Cheap extractive summary: first few sentences. Replace with an LLM call for better quality."""
    if not text:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(sentences[:max_sentences])
