from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/jobsearch"

    # Auth
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    # AI / embeddings
    embedding_model_name: str = "all-MiniLM-L6-v2"  # 384-dim, sentence-transformers
    embedding_dim: int = 384

    # File storage (local dev default; swap for S3 in prod)
    upload_dir: str = "./uploads/cvs"
    max_cv_size_mb: int = 5

    # Email (used for password reset). If smtp_host is left empty, emails are
    # printed to the backend console/log instead of actually being sent —
    # handy for local development without a real mail provider configured.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    email_from: str = "no-reply@aijobline.local"
    email_from_name: str = "AI Jobline"

    # Password reset
    password_reset_token_expire_minutes: int = 30
    frontend_base_url: str = "http://localhost:8080"  # used to build the reset link in the email

    # Cover letter drafting / assistant. If openai_api_key is left empty, cover
    # letters are generated from a template instead of a real LLM call — this
    # keeps the feature usable with zero API keys configured, same pattern as
    # the SMTP fallback above.
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # App
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    class Config:
        env_file = ".env"


settings = Settings()
