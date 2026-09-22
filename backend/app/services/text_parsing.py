"""
Small text-to-number helpers used when parsing natural-language assistant
messages ("five jobs", "the second job", "more than two years").
"""

import re

_WORD_TO_NUM = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "twenty": 20,
}

_WORD_TO_ORDINAL = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
    "1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5,
    "6th": 6, "7th": 7, "8th": 8, "9th": 9, "10th": 10,
}


def extract_search_query_text(text: str) -> str:
    """
    Strips common command/filler phrasing from a search-intent message to
    leave the actual job keywords. "Find me five suitable Java developer
    jobs" -> "Java developer". Not exhaustive NLU — covers the phrasing
    patterns typical of a job-search request.
    """
    cleaned = text.strip().rstrip(".!?")

    # Remove leading command phrases
    cleaned = re.sub(
        r"^(find me|search for|look for|show me|get me|find)\s+",
        "", cleaned, flags=re.IGNORECASE,
    )
    # Remove a leading count (digit or number word) and optional "suitable"/"good"/"open"
    cleaned = re.sub(
        r"^\s*(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+"
        r"(suitable\s+|good\s+|open\s+)?",
        "", cleaned, flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"^\s*(suitable|good|open)\s+", "", cleaned, flags=re.IGNORECASE)
    # Remove a trailing "jobs"/"job" or "positions"/"roles"
    cleaned = re.sub(r"\s+(jobs?|positions?|roles?)\s*$", "", cleaned, flags=re.IGNORECASE)

    return cleaned.strip()


def parse_number(text: str) -> int | None:
    """First digit or number-word found in text, or None."""
    digit_match = re.search(r"\b\d+\b", text)
    if digit_match:
        return int(digit_match.group())
    lowered = text.lower()
    for word, value in _WORD_TO_NUM.items():
        if re.search(rf"\b{word}\b", lowered):
            return value
    return None


def parse_ordinal_index(text: str) -> int | None:
    """
    Returns a zero-based index for an ordinal reference ("the second job" -> 1),
    or None if no ordinal is found.
    """
    lowered = text.lower()
    for word, value in _WORD_TO_ORDINAL.items():
        if re.search(rf"\b{word}\b", lowered):
            return value - 1

    # "job 2", "job #2", "job number 2", "#2"
    match = re.search(r"(?:job\s*#?\s*(?:number\s*)?|#)\s*(\d+)\b", lowered)
    if match:
        return int(match.group(1)) - 1
    return None
