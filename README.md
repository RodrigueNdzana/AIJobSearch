# AI Jobline — Job Search Engine

A full-stack job search platform with AI-powered matching: semantic job search,
CV parsing and skill detection, job recommendations, and job-to-candidate match
scoring.

```
jobsearch-app/
--- Backend/          FastAPI application (Python)
--- Frontend/          Static HTML/CSS/JS (no build step)
--- database/           PostgreSQL schema (pgvector)
--- docker-compose.yml   One-command setup for all three
--- README.md              (this file)
```

## What's inside

| Layer      | Tech                                                        |
|------------|--------------------------------------------------------------|
| Frontend   | Plain HTML, CSS, JavaScript , no framework, no build step     |
| Backend    | Python 3.12, FastAPI, SQLAlchemy (async), JWT auth             |
| Database   | PostgreSQL 16 + pgvector extension                              |
| AI / ML    | Sentence-Transformers (`all-MiniLM-L6-v2`, runs locally, free)   |

**Core features:** registration/login for job seekers, employers, and admins;
password reset via emailed link; job seeker profiles with skills; employer/company
profiles; job posting and management; job search and filtering; applications
with status tracking; notifications; CV upload with PDF/DOCX parsing.

**AI features:** semantic job search (search in plain language, not just
keywords), AI job recommendations based on your profile, automatic CV skill
detection and summarization, a hybrid job-to-candidate match score
(embedding similarity + explicit skill overlap), missing-skill identification
per job, AI-drafted cover letters, and a conversational assistant that
remembers your search history so you can ask natural-language follow-ups
like "which of these am I most qualified for?" or "draft an application for
the second job."

---

## The AI assistant

The **AI Assistant** tab on the job seeker dashboard is a chat interface that
handles the kind of follow-up questions a real job search involves:

- *"Find me five suitable Java developer jobs."* — searches and remembers the results
- *"Which of these jobs am I most qualified for?"* — ranks your last search by match score
- *"What skills am I missing?"* — compares a job's requirements against your profile
- *"Draft an application for the second job."* — resolves the ordinal against your last search and drafts a cover letter
- *"Search again and exclude jobs requiring more than two years' experience."* — refines the previous search with a new constraint

It remembers your last search per account (stored in the `search_queries`
table), so ordinal references like "the second job" resolve correctly across
turns, and the full conversation is saved (`assistant_messages`) so it's
there when you come back.

**How it understands you:** intent parsing is rule-based (pattern matching in
`app/services/text_parsing.py` and `app/services/assistant_service.py`), not
an LLM call , so the assistant works with zero API keys configured, the same
philosophy as the rest of the app's AI features. It's scoped to the
conversational patterns above and reasonable variations on them (different
counts, different ordinals, different search terms), not fully open-ended
chat. `settings.openai_api_key` (see below) is the natural place to extend
intent parsing to a real LLM for more general conversation.

---

## AI-drafted cover letters

Both the **"Draft with AI"** button on a job's detail page and the
assistant's "draft an application for..." intent call the same underlying
service (`app/services/cover_letter_service.py`):

- **No `OPENAI_API_KEY` configured (the default):** a template-based draft,
  built from your profile, the job's details, and which required skills you
  do/don't have. Deterministic, no external calls, works out of the box —
  and it's honest about skill gaps rather than hiding them.
- **`OPENAI_API_KEY` configured:** a real LLM call produces a more natural,
  genuinely customized draft. If the API call fails for any reason (bad key,
  rate limit, network error), it falls back to the template automatically —
  drafting never hard-fails.

To enable the LLM path, set in your `.env` or `docker-compose.yml`:

```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

---

## Option A: Run everything with Docker (recommended)

This starts Postgres (with pgvector), the backend API, and a static file
server for the frontend, all wired together.

**Prerequisites:** Docker and Docker Compose installed.

```bash
cd jobsearch-app
docker compose up --build
```

First startup will take a few minutes since it downloads the Sentence-Transformers
model (~90MB) the first time it's used.

Once running:
- **Frontend:** http://localhost:8080
- **Backend API:** http://localhost:8000
- **Interactive API docs:** http://localhost:8000/docs
- **Database:** localhost:5432 (user `postgres`, password `postgres`, db `jobsearch`)

The database schema is applied automatically on first startup from
`database/schema.sql`. To reset the database completely:

```bash
docker compose down -v   # -v also removes the data volume
docker compose up --build
```

---

## Option B: Run each piece manually (no Docker)

### 1. Database

Install PostgreSQL 16+ and the [pgvector](https://github.com/pgvector/pgvector)
extension, then:

```bash
createdb jobsearch
psql -d jobsearch -f database/schema.sql
```

### 2. Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: set DATABASE_URL to match your local Postgres credentials,
# and set SECRET_KEY to a long random string

uvicorn app.main:app --reload
```

The API is now running at `http://localhost:8000`. Visit
`http://localhost:8000/docs` for interactive Swagger docs covering every
endpoint. On startup, the app also auto-creates any tables that don't exist
yet — safe to leave on for development, but for a shared/production database
prefer applying `database/schema.sql` directly (Option A/B above) or move to
Alembic migrations.

### 3. Frontend

The frontend is plain static files , no build step. Serve it with any static
file server, for example:

```bash
cd frontend
python3 -m http.server 8080
```

Then open `http://localhost:8080` in your browser. The frontend is
pre-configured to call the backend at `http://localhost:8000` when accessed
via `localhost` — no extra config needed for local development.

---

## Using the app

1. **Sign up** as either a job seeker or an employer at `/register.html`.
2. **Employers:** fill out your company profile, then post a job with a
   description and required/preferred skills. The job's embedding is
   generated automatically at creation time.
3. **Job seekers:** fill out your profile (headline, summary, skills), then
   click **"Refresh recommendations embedding"** on the Profile tab. This
   recomputes your embedding so the Recommended tab and match scores reflect
   your latest info, do this again any time you meaningfully update your
   profile or skills.
4. **Search:** the homepage search bar runs semantic search ,try a full
   sentence like "remote data engineer with AWS and Python experience"
   instead of just keywords.
5. **Apply:** job seekers can upload a CV (PDF/DOCX) from their dashboard,
   it's parsed automatically, skills are detected, and a summary is
   generated. Applying to a job computes a match score from your profile
   embedding and skill overlap with the job's requirements. Try " Draft with
   AI" on a job's detail page to prefill the cover letter.
6. **Employers** review applicants sorted by match score and update their
   status (reviewed, shortlisted, interview, hired, rejected) — the
   applicant gets a notification automatically.
7. **Ask the assistant:** the AI Assistant tab handles follow-ups like
   "find me five Java developer jobs," then "which of these am I most
   qualified for?" or "draft an application for the second job" — see
   [The AI assistant](#the-ai-assistant) above for the full pattern list.

---

## Password reset

The "Forgot password?" link on the login page walks through:

1. `forgot-password.html` : enter your email, `POST /api/auth/forgot-password`.
   The response is always the same generic message ("If an account with that
   email exists...") whether or not the email is registered, so this endpoint
   can't be used to check who has an account.
2. If the email matches a real account, a reset token is generated, hashed
   (SHA-256) and stored in the `password_reset_tokens` table , the raw token
   itself is never persisted, only emailed, the same principle as a password.
   It expires after 30 minutes (`PASSWORD_RESET_TOKEN_EXPIRE_MINUTES`).
3. An email is sent with a link to `reset-password.html?token=...`.
4. `reset-password.html` submits the token and new password to
   `POST /api/auth/reset-password`, which validates the token (correct hash,
   not expired, not already used) before updating the password.

**By default, no real email is sent, and you don't need to dig through logs
to find the link.** If `SMTP_HOST` is left empty (the default in both
`.env.example` and `docker-compose.yml`), the "forgot password" page shows the
reset link directly on screen, right under the success message, as soon as
you submit the form. The backend also logs it to its console
(`docker compose logs backend`) as a backup. This means the whole flow works
out of the box for local development and testing with zero setup — register
a user, request a reset, click the link that appears on the page.

The moment you configure `SMTP_HOST` (see below), that on-screen link
disappears and a real email goes out instead — the on-screen link only ever
appears when no mail server is configured, so it's safe to leave this
default in place while developing without accidentally shipping it to
production.

To send real email to your mailbox, set these in your `.env` (manual setup) or in the
`backend.environment` block of `docker-compose.yml`:

```
SMTP_HOST=smtp.yourprovider.com
SMTP_PORT=587
SMTP_USERNAME=your-username
SMTP_PASSWORD=your-password
EMAIL_FROM=no-reply@yourdomain.com
```

Any standard SMTP provider works , Gmail (with an
[app password](https://support.google.com/accounts/answer/185833)), SendGrid,
Postmark, AWS SES, etc. Also make sure `FRONTEND_BASE_URL` points at wherever
you're actually serving the `frontend/` folder, since it's used to build the
link inside the email.

---

## Project structure in detail

### `backend/app/`
- `models/` — SQLAlchemy ORM models (mirrors `database/schema.sql` exactly)
- `schemas/` — Pydantic request/response validation
- `routers/` — API endpoints, grouped by resource (`auth`, `job_seekers`,
  `employers`, `jobs`, `applications`, `cvs`, `notifications`, `assistant`)
- `services/` — business logic: `embedding_service.py` (wraps
  Sentence-Transformers), `matching_service.py` (semantic search, hybrid
  match scoring, missing-skill identification), `cv_parser.py` (PDF/DOCX text
  extraction), `cv_analysis.py` (skill detection + summarization),
  `requirement_extraction.py` (mines a minimum years-of-experience threshold
  out of free-text job ads), `cover_letter_service.py` (template or LLM-based
  cover letter drafting), `text_parsing.py` and `assistant_service.py` (the
  conversational assistant's intent parsing and execution), `email_service.py`
  (password reset)
- `core/` — JWT auth (`security.py`) and role-based access control
  (`dependencies.py`)
- `main.py` — app entrypoint, wires up all routers and CORS

### `frontend/`
- `index.html` — public job search/browse page
- `login.html`, `register.html` — auth pages
- `forgot-password.html`, `reset-password.html` — password reset flow
- `job-detail.html` — job details + apply flow, with an AI cover-letter draft button
- `seeker-dashboard.html` — job seeker's recommendations, **AI Assistant
  chat**, applications, profile, CVs, notifications (tabbed)
- `employer-dashboard.html` — employer's job postings, applicant review,
  job posting form, company profile (tabbed)
- `js/api.js` — fetch wrapper handling auth tokens and JSON parsing
- `js/header.js` — shared nav bar, adapts to auth state and role

### `database/schema.sql`
Full PostgreSQL DDL: all tables, enums, indexes (including `ivfflat` vector
indexes for embedding similarity search), triggers for `updated_at`
timestamps, and a small seed set of common skills.

---

## Extending this further

A few things intentionally left as follow-ups rather than built in, since
they depend on decisions specific to your deployment:

- **Admin panel** :the `admin` role and audit log table exist in the schema,
  but there's no admin UI yet. A natural next step: endpoints to
  deactivate users, remove listings, and view the `admin_audit_log` table.
- **File storage** : CVs currently save to local disk (`UPLOAD_DIR`). Swap
  for S3 or similar before deploying to more than one server instance.
- **CV summary quality** — `cv_analysis.py` uses a simple extractive
  summary (first few sentences). Swap in a call to an LLM (OpenAI, Claude,
  or a local model) for a genuinely abstractive summary.
- **Migrations** : the app uses `create_all()` on startup for convenience.
  For a real deployment, switch to [Alembic](https://alembic.sqlalchemy.org/)
  so schema changes are tracked and reversible.
- **Embedding model** : defaults to `all-MiniLM-L6-v2` (384 dimensions,
  free, runs locally). To use OpenAI's `text-embedding-3-small` instead,
  update `embed_text()`/`embed_batch()` in `embedding_service.py` and change
  `EMBEDDING_DIM` to 1536 in both `.env` and `database/schema.sql`'s
  `vector(384)` columns.
- **Assistant conversation scope** : the assistant's intent parsing
  (`text_parsing.py`, `assistant_service.py`) is rule-based, covering the
  search/rank/missing-skills/draft/refine patterns and reasonable variations.
  For genuinely open-ended conversation, swap `classify_intent()` for an LLM
  call using `settings.openai_api_key` (already wired up for cover letters).
