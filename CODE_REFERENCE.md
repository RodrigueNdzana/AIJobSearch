# Code Reference — What Each File Does

A file-by-file guide to the project. Organized by folder, in the order you'd
typically read them.

---

## `database/`

| File | What it does |
|---|---|
| `schema.sql` | The full PostgreSQL DDL: every table (`users`, `job_seekers`, `employers`, `jobs`, `skills`, `cvs`, `applications`, `notifications`, `saved_jobs`, `password_reset_tokens`, `search_queries`, `assistant_messages`, `admin_audit_log`), enum types, indexes (including `ivfflat` vector indexes for embedding similarity search), `updated_at` triggers, and a seed list of common skills. `jobs` also carries `min_experience_years`, set explicitly or auto-extracted from free-text requirements at posting time. This is the single source of truth for the data model — the SQLAlchemy models in `backend/app/models/` mirror it exactly. |

---

## `backend/` : FastAPI application

### Root

| File | What it does |
|---|---|
| `Dockerfile` | Builds the backend container: Python 3.12 slim base, installs system build tools (needed by `sentence-transformers`), installs `requirements.txt`, copies the app, runs `uvicorn` on port 8000. |
| `requirements.txt` | Pinned Python dependencies. Notably pins `bcrypt==4.0.1` alongside `passlib[bcrypt]==1.7.4` — newer bcrypt versions (4.1+) break passlib's backend self-test, so this pin is load-bearing, not cosmetic. |
| `.env.example` | Template for local environment variables (database URL, JWT secret, embedding model name, upload dir, CORS origins). Copy to `.env` and fill in for local (non-Docker) runs. |

### `app/` : core

| File | What it does |
|---|---|
| `main.py` | App entrypoint. Creates the FastAPI app, registers CORS middleware, includes every router, and on startup calls `Base.metadata.create_all()` to auto-create tables (dev convenience — swap for Alembic migrations in production). Also defines `GET /health`. |
| `config.py` | `Settings` class (pydantic-settings) reading all configuration from environment variables / `.env`: database URL, JWT secret and expiry, embedding model name and dimension, upload directory, CORS origins, and SMTP/email settings for password reset (`smtp_host` etc. — leaving `smtp_host` empty makes reset emails log to console instead of sending). |
| `database.py` | Sets up the async SQLAlchemy engine and session factory, defines the `Base` declarative class every model inherits from, and provides the `get_db()` FastAPI dependency that yields a request-scoped DB session. |

### `app/models/` : SQLAlchemy ORM models (mirror `schema.sql`)

| File | What it does |
|---|---|
| `__init__.py` | Imports every model so `Base.metadata` knows about all of them before `create_all()` runs. |
| `user.py` | `User` model — email, password hash, `role` enum (`job_seeker`/`employer`/`admin`), active/verified flags. |
| `job_seeker.py` | `JobSeeker` model — 1:1 extension of `User`. Profile fields (headline, summary, experience, location) plus `profile_embedding`, a pgvector `Vector(384)` column used for semantic recommendations. |
| `employer.py` | `Employer` model — 1:1 extension of `User`. Company profile fields (name, industry, size, website, description). |
| `skill.py` | Three things: the `Skill` master taxonomy table, `JobSeekerSkill` (junction: which skills a seeker has, with proficiency), and `JobSkill` (junction: which skills a job requires, required vs. preferred). |
| `job.py` | `Job` model — title, description, requirements, location, salary range, `job_type`/`status` enums, `min_experience_years` (explicit or auto-extracted), and an `embedding` `Vector(384)` column generated from the job text at creation time. |
| `cv.py` | `CV` model — uploaded file metadata, `parsed_text` (extracted from PDF/DOCX), `parsed_summary`, and its own `embedding` column, separate from the profile embedding. |
| `application.py` | `Application` model — links a `Job` and a `JobSeeker`, cover letter, `status` enum, and the stored `match_score` (computed once at application time, not recalculated on every read). |
| `notification.py` | `Notification`,   model in-app notifications tied to a user, with `type`, title/message, and a read flag. |
| `saved_job.py` | `SavedJob` — simple many-to-many junction for bookmarking jobs. |
| `search_query.py` | `SearchQuery` model — remembers a job seeker's past searches: the query text, structured filters applied, and an ordered list of the resulting job IDs. This is what lets the assistant resolve "the second job" and "search again" across turns. |
| `assistant_message.py` | `AssistantMessage` model — the conversation transcript (`role`: user/assistant, `content`) for the AI assistant chat, persisted so history survives a page refresh. |
| `password_reset_token.py` | `PasswordResetToken` model : stores a hashed reset token (never the raw token), its expiry, and when it was used (`used_at`, so a token can't be replayed). |

### `app/schemas/` :  Pydantic request/response models

| File | What it does |
|---|---|
| `auth.py` | `UserRegister`, `UserLogin`, `Token`, `UserOut`, `ForgotPasswordRequest`, `ResetPasswordRequest` — shapes for the register/login/password-reset endpoints. |
| `job_seeker.py` | `JobSeekerUpdate`, `JobSeekerOut`, `SkillIn`/`SkillOut` ,profile editing and skill list shapes. |
| `employer.py` | `EmployerUpdate`, `EmployerOut` — company profile shapes. |
| `job.py` | `JobCreate`, `JobUpdate`, `JobOut`, `JobSearchQuery`, `JobSearchResult` — job posting and search shapes. `JobCreate`/`JobOut` carry `min_experience_years`; `JobSearchQuery` carries `max_experience_years` (excludes jobs requiring more than N years). `JobSearchResult` extends `JobOut` with an optional `similarity_score`. |
| `application.py` | `ApplicationCreate`, `ApplicationStatusUpdate`, `ApplicationOut` — applying and status-tracking shapes. |
| `cv.py` | `CVOut`, `CVAnalysis` — CV listing and the AI-analysis response returned right after upload (detected skills, summary, word count). |
| `notification.py` | `NotificationOut` — notification list shape. |
| `assistant.py` | `AssistantChatRequest`/`AssistantChatResponse` (chat turn in/out — reply text, job cards, missing skills, cover letter), `AssistantMessageOut` (transcript entry shape). |

### `app/core/` : auth infrastructure

| File | What it does |
|---|---|
| `security.py` | Password hashing/verification (bcrypt via passlib), JWT creation/decoding (`create_access_token`, `decode_access_token`), and password-reset token generation/hashing (`generate_reset_token`, `hash_reset_token` — SHA-256, same never-store-the-raw-value principle as passwords). |
| `dependencies.py` | `get_current_user` (decodes the bearer token, loads the user) and `require_role(*roles)` — a dependency factory used throughout the routers to enforce role-based access (e.g. only employers can post jobs). |

### `app/services/` : business logic, independent of HTTP

| File | What it does |
|---|---|
| `embedding_service.py` | Wraps Sentence-Transformers (`all-MiniLM-L6-v2` by default). `embed_text()`/`embed_batch()` generate vectors; `build_job_seeker_text()`/`build_job_text()` compose the text that gets embedded from profile/job fields. This is the one file to edit if you swap in OpenAI embeddings instead. |
| `matching_service.py` | The AI matching core. `semantic_job_search()` runs a pgvector cosine-distance query (`<=>` operator). `run_job_search()` is the shared search+filter logic used by both the `/api/jobs/search` endpoint and the assistant (so "search again" reuses exactly the same filtering, including `max_experience_years`). `recommend_jobs_for_seeker()` uses a seeker's `profile_embedding` to rank open jobs. `compute_match_score()` blends 60% embedding similarity with 40% required-skill overlap into a single 0–100 score (guards against NaN if an embedding is degenerate, so it never displays as "nan%"). `get_missing_skills()` returns the required/preferred skills a job asks for that aren't on the seeker's profile. |
| `cv_parser.py` | Extracts raw text from uploaded CVs — `pypdf` for PDF, `python-docx` for DOCX. Isolated so the upload endpoint can catch parsing failures without crashing the request. |
| `cv_analysis.py` | `detect_skills()` matches parsed CV text against the `skills` taxonomy by substring/word-boundary search. `summarize()` is a simple extractive summary (first N sentences) — flagged in comments as the place to swap in a real LLM call for better quality. |
| `requirement_extraction.py` | `extract_min_experience_years()` — regex-based extraction of a minimum years-of-experience threshold from free-text job requirements/descriptions ("5+ years", "at least 3 years", "1 year of Java experience"). Runs automatically at job creation when the employer doesn't set `min_experience_years` explicitly. |
| `cover_letter_service.py` | Cover letter drafting. `draft_cover_letter_for_job()` is the entry point — looks up the company name and computes matched/missing skills, then calls `draft_cover_letter()`, which uses a template (`_template_cover_letter()`) by default or a real LLM call (`_llm_cover_letter()`, OpenAI) if `settings.openai_api_key` is set. Falls back to the template automatically if the LLM call fails for any reason. |
| `text_parsing.py` | Small NLU helpers for the assistant: `parse_number()` (digits or number-words → int), `parse_ordinal_index()` ("the second job" → zero-based index 1), `extract_search_query_text()` (strips command/filler phrasing to leave the actual search keywords). |
| `assistant_service.py` | The conversational assistant's core logic. `classify_intent()` routes a message to one of five intents via keyword/pattern matching (search, rank-by-match, missing-skills, draft-application, refine-search). Each `handle_*()` function executes that intent against the existing search/matching/cover-letter services and returns an `AssistantResult` (reply text + structured data). Remembers the seeker's last search (via `SearchQuery`) so ordinal references and refinements work across turns. |
| `email_service.py` | Sends transactional email (currently just password-reset). If `SMTP_HOST` isn't set, emails are logged to the console instead of sent the whole reset flow works out of the box without real mail credentials configured. `send_password_reset_email()` builds the HTML/text email; `send_email()` is the generic SMTP sender underneath it. |

### `app/routers/` — HTTP endpoints, grouped by resource

| File | Endpoints | What it does |
|---|---|---|
| `auth.py` | `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/forgot-password`, `POST /api/auth/reset-password` | Registration creates the `User` row plus the matching `JobSeeker`/`Employer` extension row in one transaction; blocks self-registering as `admin`. Login uses OAuth2 form data (not JSON) per FastAPI convention and returns a JWT. `forgot-password` always returns the same generic message regardless of whether the email exists (prevents account enumeration) and emails a time-limited reset link if it does; when no SMTP server is configured, it also returns the link directly as `dev_reset_link` so the flow is usable without a mail server. `reset-password` validates the token (hash match, not expired, not already used) before updating the password. |
| `job_seekers.py` | `GET/PATCH /api/job-seekers/me`, `GET/POST /api/job-seekers/me/skills`, `DELETE /api/job-seekers/me/skills/{id}`, `POST /api/job-seekers/me/refresh-embedding` | Profile CRUD, skill management, and the endpoint that recomputes `profile_embedding` from the current headline/summary/skills — call this after any profile edit so recommendations stay current. |
| `employers.py` | `GET/PATCH /api/employers/me` | Company profile CRUD. |
| `jobs.py` | `POST /api/jobs`, `GET/PATCH /api/jobs/{id}`, `GET /api/jobs/{id}/missing-skills`, `GET /api/jobs/employer/me`, `GET /api/jobs/recommendations/me`, `POST /api/jobs/search` | Job posting (embeds the job text and auto-extracts `min_experience_years` on creation), missing-skills lookup for a job vs. the current seeker, the employer's own listings, AI recommendations (semantic search against the seeker's profile embedding), and hybrid search (semantic when a `query` is given, structured filters — including `max_experience_years` — always apply). **Route order matters here** — the specific routes (`/employer/me`, `/recommendations/me`, `/search`, and `/{job_id}/missing-skills`) are declared before the generic `/{job_id}` route so they aren't swallowed by it. |
| `applications.py` | `POST /api/applications`, `POST /api/applications/draft-cover-letter`, `GET /api/applications/me`, `GET /api/applications/job/{job_id}`, `PATCH /api/applications/{id}/status` | Applying (computes `match_score` at submission time, defaults to the seeker's primary CV), AI cover-letter drafting for a job without submitting an application, a seeker's own applications, an employer's view of applicants for one job (sorted by match score), and status updates — each triggers a `Notification` to the other party. |
| `cvs.py` | `POST /api/cvs/upload`, `GET /api/cvs/me`, `PATCH /api/cvs/{id}/set-primary`, `DELETE /api/cvs/{id}` | CV upload: extracts text, detects skills, generates a summary, embeds it, saves the file to local disk, and auto-marks the first upload as primary. Malformed files degrade gracefully (file still saves, AI enrichment just skipped) rather than 500ing. |
| `notifications.py` | `GET /api/notifications`, `PATCH /api/notifications/{id}/read`, `PATCH /api/notifications/read-all` | Listing (with an `unread_only` filter) and marking notifications read. |
| `assistant.py` | `POST /api/assistant/chat`, `GET /api/assistant/history` | The conversational assistant endpoint — persists both sides of each turn to `assistant_messages`, then delegates to `assistant_service.handle_message()`. `history` returns the full transcript for a seeker so the chat UI can restore it on page load. |

---

## `frontend/` :  static HTML/CSS/JS, no build step

### Pages

| File | What it does |
|---|---|
| `index.html` | Public landing/browse page. Search bar posts to `/api/jobs/search` (semantic when text is entered), plus structured filters (type, remote, location, salary). No auth required. |
| `login.html` | Login form. On success, probes `/api/job-seekers/me` then `/api/employers/me` to determine the user's role (there's no dedicated `/me` endpoint yet), stores the JWT and role in `localStorage`, redirects to the right dashboard. Has a "Forgot password?" link. |
| `register.html` | Registration form with a role selector that relabels the name field ("Full name" vs. "Company name") depending on role. |
| `forgot-password.html` | Enter your email, `POST /api/auth/forgot-password`. Always shows the same generic success message regardless of whether the email exists, matching the backend's anti-enumeration behavior. When the response includes `dev_reset_link` (no SMTP configured), displays that link directly on the page so the flow is testable with zero mail-server setup. |
| `reset-password.html` | Reads the reset `token` from the URL query string, takes a new password (with confirm-match check client-side), and `POST`s to `/api/auth/reset-password`. Shows an error and hides the form if no token is present in the URL. |
| `job-detail.html` | Job details plus the apply flow. Shows a login CTA if logged out, a "job seekers only" notice for employer accounts, or the cover-letter + submit form for job seekers, with a "✨ Draft with AI" button that calls `/api/applications/draft-cover-letter` to prefill the cover letter. |
| `seeker-dashboard.html` | Shell page with six tabs (Recommended, **AI Assistant**, Applications, Profile, CVs, Notifications); all logic lives in `js/seeker-dashboard.js`. |
| `employer-dashboard.html` | Shell page with four tabs (My postings, Post a job, Company profile, Notifications) plus a modal for reviewing applicants; logic in `js/employer-dashboard.js`. |

### `css/`

| File | What it does |
|---|---|
| `styles.css` | The whole design system: CSS custom properties for the "ledger" color palette (ink navy, parchment paper, teal accent, amber for status), typography (Fraunces for headings, Inter for body, IBM Plex Mono for the eyebrow/match-badge labels), and every component class (`.job-card`, `.pill`, `.tab-row`, `.card`, form elements, etc.) used across all pages. |

### `js/`

| File | What it does |
|---|---|
| `api.js` | The shared API client. `Api.request()` wraps `fetch`, auto-attaches the bearer token, parses JSON, and throws readable errors. `Api.login()` handles the OAuth2 form-encoded login endpoint specially. Also has `requireAuth()`/`requireRole()` guards, `logout()`, and small formatting helpers (`formatDate`, `formatSalary`, `jobTypeLabel`, `escapeHtml`). |
| `header.js` | `renderHeader()`, builds the nav bar HTML based on auth state and role, injected into `#site-header` on every page. |
| `seeker-dashboard.js` | All six tab behaviors for the job seeker dashboard: fetching/rendering recommendations and applications, the profile edit form, skill add/remove, the "refresh embedding" action, CV upload/list/set-primary/delete, notifications, and the **AI Assistant** chat (sends messages to `/api/assistant/chat`, loads history on first open, renders job cards/missing skills/cover letters inline in the chat bubbles). |
| `employer-dashboard.js` | All four tab behaviors for the employer dashboard: listing/publishing/closing job postings, the applicant-review modal (status dropdown per applicant), the post-a-job form, company profile editing, and notifications. |

---

## Root

| File | What it does |
|---|---|
| `docker-compose.yml` | Orchestrates three services: `db` (pgvector/pgvector:pg16, auto-loads `database/schema.sql` on first start via the Postgres init-scripts convention), `backend` (builds from `backend/Dockerfile`), and `frontend` (a plain Python `http.server` serving the static files). Backend waits for the DB healthcheck before starting. |
| `.gitignore` | Standard excludes: `__pycache__`, virtualenvs, `.env`, local CV uploads, OS/editor cruft. |
| `README.md` | Full setup instructions (Docker and manual), a feature overview, usage walkthrough, and a list of intentional follow-ups (admin UI, S3 storage, Alembic migrations, etc.) with reasoning for why each was left out of this scaffold. |
