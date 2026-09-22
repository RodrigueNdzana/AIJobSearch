-- ============================================================
-- AI Job Search Engine — PostgreSQL Schema
-- Requires: PostgreSQL 15+, pgvector extension
-- ============================================================

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- ENUM TYPES
-- ============================================================

CREATE TYPE user_role AS ENUM ('job_seeker', 'employer', 'admin');
CREATE TYPE job_type AS ENUM ('full_time', 'part_time', 'contract', 'internship', 'remote', 'freelance');
CREATE TYPE job_status AS ENUM ('draft', 'open', 'closed', 'expired');
CREATE TYPE application_status AS ENUM ('pending', 'reviewed', 'shortlisted', 'interview', 'rejected', 'hired', 'withdrawn');
CREATE TYPE proficiency_level AS ENUM ('beginner', 'intermediate', 'advanced', 'expert');
CREATE TYPE notification_type AS ENUM ('application_status', 'new_job_match', 'new_applicant', 'system', 'message');

-- ============================================================
-- 1. USERS  (auth + role, shared by all account types)
-- ============================================================

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    role            user_role NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    is_verified     BOOLEAN NOT NULL DEFAULT FALSE,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);

-- ============================================================
-- 1b. PASSWORD RESET TOKENS
-- ============================================================

CREATE TABLE password_reset_tokens (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash      VARCHAR(255) NOT NULL,          -- SHA-256 hash of the token; raw token is only ever emailed, never stored
    expires_at      TIMESTAMPTZ NOT NULL,
    used_at         TIMESTAMPTZ,                     -- set when the token is consumed; NULL means still valid/unused
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_password_reset_tokens_user ON password_reset_tokens(user_id);
CREATE INDEX idx_password_reset_tokens_hash ON password_reset_tokens(token_hash);

-- ============================================================
-- 2. JOB SEEKERS  (1:1 extension of users where role = job_seeker)
-- ============================================================

CREATE TABLE job_seekers (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id             UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    full_name           VARCHAR(150) NOT NULL,
    phone               VARCHAR(30),
    location            VARCHAR(150),
    headline            VARCHAR(200),              -- e.g. "Senior Backend Engineer"
    summary             TEXT,                       -- bio / about
    experience_years    NUMERIC(4,1),
    education_level     VARCHAR(100),
    portfolio_url       VARCHAR(255),
    linkedin_url        VARCHAR(255),
    profile_embedding   vector(384),                -- Sentence-Transformers all-MiniLM-L6-v2 = 384 dims
    is_open_to_work     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_job_seekers_user ON job_seekers(user_id);
CREATE INDEX idx_job_seekers_embedding ON job_seekers USING ivfflat (profile_embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================================
-- 3. EMPLOYERS  (1:1 extension of users where role = employer)
-- ============================================================

CREATE TABLE employers (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id             UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    company_name        VARCHAR(200) NOT NULL,
    company_description TEXT,
    industry            VARCHAR(100),
    company_size        VARCHAR(50),                -- e.g. "51-200"
    website_url         VARCHAR(255),
    logo_url            VARCHAR(255),
    location            VARCHAR(150),
    is_verified         BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_employers_user ON employers(user_id);

-- ============================================================
-- 4. SKILLS  (master taxonomy, shared across seekers & jobs)
-- ============================================================

CREATE TABLE skills (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    category    VARCHAR(100)                        -- e.g. "Programming Language", "Soft Skill"
);

CREATE INDEX idx_skills_name ON skills(name);

-- Job seeker <-> Skills (many-to-many)
CREATE TABLE job_seeker_skills (
    job_seeker_id   UUID NOT NULL REFERENCES job_seekers(id) ON DELETE CASCADE,
    skill_id        INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    proficiency     proficiency_level NOT NULL DEFAULT 'intermediate',
    years_used      NUMERIC(4,1),
    PRIMARY KEY (job_seeker_id, skill_id)
);

-- ============================================================
-- 5. JOBS
-- ============================================================

CREATE TABLE jobs (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    employer_id         UUID NOT NULL REFERENCES employers(id) ON DELETE CASCADE,
    title               VARCHAR(200) NOT NULL,
    description         TEXT NOT NULL,
    responsibilities    TEXT,
    requirements        TEXT,
    location            VARCHAR(150),
    is_remote           BOOLEAN NOT NULL DEFAULT FALSE,
    job_type            job_type NOT NULL DEFAULT 'full_time',
    salary_min          NUMERIC(12,2),
    salary_max          NUMERIC(12,2),
    currency            VARCHAR(10) DEFAULT 'USD',
    experience_level    VARCHAR(50),                 -- entry / mid / senior / lead
    min_experience_years NUMERIC(4,1),                -- explicit, or auto-extracted from requirements text at posting time (see requirement_extraction service)
    status              job_status NOT NULL DEFAULT 'draft',
    embedding           vector(384),                 -- embedding of title+description+requirements
    views_count         INTEGER NOT NULL DEFAULT 0,
    posted_at           TIMESTAMPTZ,
    expires_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_jobs_employer ON jobs(employer_id);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_location ON jobs(location);
CREATE INDEX idx_jobs_type ON jobs(job_type);
CREATE INDEX idx_jobs_embedding ON jobs USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
-- Full-text fallback search (in addition to semantic search)
CREATE INDEX idx_jobs_fulltext ON jobs USING GIN (to_tsvector('english', title || ' ' || description));

-- Jobs <-> Skills (many-to-many, required vs nice-to-have)
CREATE TABLE job_skills (
    job_id          UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    skill_id        INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    is_required     BOOLEAN NOT NULL DEFAULT TRUE,
    min_proficiency proficiency_level NOT NULL DEFAULT 'intermediate',
    PRIMARY KEY (job_id, skill_id)
);

-- ============================================================
-- 6. CVs  (a job seeker may upload multiple; one marked primary)
-- ============================================================

CREATE TABLE cvs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_seeker_id   UUID NOT NULL REFERENCES job_seekers(id) ON DELETE CASCADE,
    file_name       VARCHAR(255) NOT NULL,
    file_url        VARCHAR(500) NOT NULL,           -- path/URL in object storage (S3, etc.)
    file_type       VARCHAR(20),                     -- pdf / docx
    parsed_text     TEXT,                             -- extracted raw text
    parsed_summary  TEXT,                             -- AI-generated summary of the CV
    embedding       vector(384),                      -- embedding of parsed CV text
    is_primary      BOOLEAN NOT NULL DEFAULT FALSE,
    uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_cvs_job_seeker ON cvs(job_seeker_id);
CREATE INDEX idx_cvs_embedding ON cvs USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
-- Only one primary CV per job seeker
CREATE UNIQUE INDEX idx_cvs_one_primary ON cvs(job_seeker_id) WHERE is_primary = TRUE;

-- ============================================================
-- 7. APPLICATIONS
-- ============================================================

CREATE TABLE applications (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id          UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    job_seeker_id   UUID NOT NULL REFERENCES job_seekers(id) ON DELETE CASCADE,
    cv_id           UUID REFERENCES cvs(id) ON DELETE SET NULL,
    cover_letter    TEXT,
    status          application_status NOT NULL DEFAULT 'pending',
    match_score     NUMERIC(5,2),                    -- 0-100, computed at application time
    employer_notes  TEXT,                             -- internal notes, not visible to seeker
    applied_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (job_id, job_seeker_id)                    -- one application per job per seeker
);

CREATE INDEX idx_applications_job ON applications(job_id);
CREATE INDEX idx_applications_seeker ON applications(job_seeker_id);
CREATE INDEX idx_applications_status ON applications(status);

-- ============================================================
-- 8. NOTIFICATIONS
-- ============================================================

CREATE TABLE notifications (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type                notification_type NOT NULL,
    title               VARCHAR(200) NOT NULL,
    message             TEXT NOT NULL,
    related_entity_type VARCHAR(50),                 -- 'job', 'application', etc.
    related_entity_id   UUID,
    is_read             BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_notifications_user ON notifications(user_id, is_read);

-- ============================================================
-- 9. SAVED / BOOKMARKED JOBS (nice-to-have, common feature)
-- ============================================================

CREATE TABLE saved_jobs (
    job_seeker_id   UUID NOT NULL REFERENCES job_seekers(id) ON DELETE CASCADE,
    job_id          UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    saved_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (job_seeker_id, job_id)
);

-- ============================================================
-- 10. SEARCH QUERIES (job seeker's search memory — "find these again", filters reused on refinement)
-- ============================================================

CREATE TABLE search_queries (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_seeker_id   UUID NOT NULL REFERENCES job_seekers(id) ON DELETE CASCADE,
    query_text      TEXT,                             -- free-text query, if any (semantic search input)
    filters         JSONB,                             -- structured filters applied (job_type, location, max_experience_years, etc.)
    result_job_ids  JSONB NOT NULL DEFAULT '[]',        -- ordered array of job UUIDs returned, so "the second job" can be resolved later
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_search_queries_seeker ON search_queries(job_seeker_id, created_at DESC);

-- ============================================================
-- 11. ASSISTANT MESSAGES (conversation transcript for the AI job-search assistant)
-- ============================================================

CREATE TYPE assistant_role AS ENUM ('user', 'assistant');

CREATE TABLE assistant_messages (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_seeker_id   UUID NOT NULL REFERENCES job_seekers(id) ON DELETE CASCADE,
    role            assistant_role NOT NULL,
    content         TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_assistant_messages_seeker ON assistant_messages(job_seeker_id, created_at);

-- ============================================================
-- 12. AUDIT LOG (admin oversight of platform actions)
-- ============================================================

CREATE TABLE admin_audit_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    admin_user_id   UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action          VARCHAR(100) NOT NULL,           -- e.g. "deactivated_user", "removed_job"
    target_type     VARCHAR(50),
    target_id       UUID,
    details         JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- TRIGGER: auto-update `updated_at` columns
-- ============================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_job_seekers_updated_at BEFORE UPDATE ON job_seekers
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_employers_updated_at BEFORE UPDATE ON employers
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_jobs_updated_at BEFORE UPDATE ON jobs
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_applications_updated_at BEFORE UPDATE ON applications
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- SEED: common skills categories (optional starter data)
-- ============================================================

INSERT INTO skills (name, category) VALUES
    ('Python', 'Programming Language'),
    ('JavaScript', 'Programming Language'),
    ('SQL', 'Programming Language'),
    ('FastAPI', 'Framework'),
    ('React', 'Framework'),
    ('PostgreSQL', 'Database'),
    ('Docker', 'DevOps'),
    ('Communication', 'Soft Skill'),
    ('Project Management', 'Soft Skill')
ON CONFLICT (name) DO NOTHING;
