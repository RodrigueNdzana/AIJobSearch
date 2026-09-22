from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base
import app.models  # noqa: F401 — ensures all models are registered on Base.metadata
from app.routers import applications, assistant, auth, cvs, employers, job_seekers, jobs, notifications


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Dev convenience only — use Alembic migrations in production instead of create_all.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="AI Job Search Engine", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(job_seekers.router)
app.include_router(employers.router)
app.include_router(jobs.router)
app.include_router(applications.router)
app.include_router(cvs.router)
app.include_router(notifications.router)
app.include_router(assistant.router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
