"""
Generates vector embeddings for job seeker profiles, CVs, and job postings.

Uses Sentence-Transformers locally (free, no API key, 384-dim with the default
model). To swap in OpenAI's text-embedding-3-small instead, replace the encode()
body with an API call and update EMBEDDING_DIM in app/config.py to 1536.
"""

from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.config import settings


@lru_cache(maxsize=1)
def get_model() -> SentenceTransformer:
    # Loaded once per process; lru_cache keeps the model resident in memory.
    return SentenceTransformer(settings.embedding_model_name)


def embed_text(text: str) -> list[float]:
    """Return a single embedding vector for a piece of text."""
    if not text or not text.strip():
        return [0.0] * settings.embedding_dim
    model = get_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Batch-embed multiple texts at once (much faster than looping embed_text)."""
    model = get_model()
    vectors = model.encode(texts, normalize_embeddings=True, batch_size=32)
    return [v.tolist() for v in vectors]


def build_job_seeker_text(headline: str | None, summary: str | None, skills: list[str]) -> str:
    """Compose the text that gets embedded for a job seeker's profile_embedding."""
    parts = [headline or "", summary or "", "Skills: " + ", ".join(skills)]
    return "\n".join(p for p in parts if p.strip())


def build_job_text(title: str, description: str, requirements: str | None, skills: list[str]) -> str:
    """Compose the text that gets embedded for a job's embedding column."""
    parts = [title, description, requirements or "", "Required skills: " + ", ".join(skills)]
    return "\n".join(p for p in parts if p.strip())
