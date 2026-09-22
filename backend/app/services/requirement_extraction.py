"""
Extracts structured requirements from unstructured job advertisement text.
Required/preferred skills are already captured as structured input at
posting time (see JobCreate.required_skills/preferred_skills) — this module
covers the piece that ISN'T already structured: a minimum years-of-experience
threshold, mined from free-text requirements/description via regex.

This runs automatically at job creation when the employer doesn't explicitly
set min_experience_years, so "requirements are extracted from the ad" holds
even for postings written as plain prose ("5+ years of backend experience...").
"""

import re

# Matches patterns like "5+ years", "5 years", "at least 5 years",
# "minimum of 5 years", "5-7 years" (takes the lower bound).
_PATTERNS = [
    re.compile(r"(?:at least|minimum of|min\.?)\s+(\d+)\+?\s*years?", re.IGNORECASE),
    re.compile(r"(\d+)\s*\+\s*years?", re.IGNORECASE),
    re.compile(r"(\d+)\s*-\s*\d+\s*years?", re.IGNORECASE),
    # "X years [of <anything up to ~30 chars, same sentence>] experience" —
    # allows a skill/tech name between "years of" and "experience", e.g.
    # "1 year of Java experience".
    re.compile(r"(\d+)\s*years?\b[^.]{0,30}?\bexp(?:erience)?\.?", re.IGNORECASE),
]


def extract_min_experience_years(*texts: str | None) -> float | None:
    """
    Scans the given text(s) for the earliest/lowest explicit years-of-experience
    requirement it can find. Returns None if nothing matches — callers should
    treat that as "no extractable threshold", not "zero years required".
    """
    combined = " ".join(t for t in texts if t)
    if not combined:
        return None

    candidates: list[float] = []
    for pattern in _PATTERNS:
        for match in pattern.finditer(combined):
            try:
                candidates.append(float(match.group(1)))
            except (ValueError, IndexError):
                continue

    if not candidates:
        return None
    return min(candidates)
