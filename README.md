# INNOVATE-GOV — SIH26136

An AI-powered innovation procurement platform for the Government of
Maharashtra: it converts government problems into structured, KPI-bearing
"challenges," uses a real (non-random) AI matching pipeline to discover and
rank suitable startups, manages document verification and expert evaluation,
runs controlled pilots with milestone/KPI tracking, and produces an
explainable Scale/Modify/Reject recommendation at the end of each pilot —
building a searchable knowledge base of past pilots along the way.

**Problem Statement:** Government departments struggle to discover and
procure innovative startup solutions because traditional procurement is
designed for established vendors and standardized products. Startups face
strict eligibility requirements, long procurement cycles, and no visibility
into what departments actually need.

**End-to-end journey implemented:** Government Problem → Structured Challenge
→ AI Startup Discovery & Matching → Document Verification → Proposal
Submission → Expert Evaluation → Shortlisting → Controlled Pilot →
Milestones/Contracts/Payments → KPI & Impact Tracking → Scale/Modify/Reject
Recommendation → Knowledge Base of Past Pilots.

## Architecture at a glance

```
React (Vite/TS/Tailwind) ──▶ Spring Boot backend ──▶ FastAPI AI service
                                     │                        │
                                     └────────▶ PostgreSQL ◀──┘
```

Full detail: [`docs/architecture.md`](docs/architecture.md) ·
[`docs/db-schema.md`](docs/db-schema.md) ·
[`docs/api.md`](docs/api.md) ·
[`docs/ai-matching.md`](docs/ai-matching.md) — the AI matching write-up in
particular is worth reading before the demo; it documents the exact weighted
formula and every deliberate deviation from the reference spec.

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS v4, Radix UI primitives, Recharts, React Router |
| Backend | Spring Boot 3.5 (Java 21), Spring Security (JWT), Spring Data JPA, Hibernate |
| AI service | FastAPI, sentence-transformers (`all-MiniLM-L6-v2`), numpy, SQLAlchemy |
| Database | PostgreSQL 17 |
| Auth | JWT (HS256), bcrypt password hashing |

## Two important engineering decisions (read before running)

1. **No pgvector.** The reference spec calls for pgvector. This project's
   build environment had no Docker and no working MSVC build toolchain to
   compile the extension, and no pre-built Windows binary exists for it.
   Embeddings are stored as plain `double precision[]` columns; cosine
   similarity is computed in the AI service with numpy — real, exact,
   reproducible math, just without an ANN index (which only matters at a much
   larger scale than this seed dataset). Full rationale in
   [`docs/ai-matching.md`](docs/ai-matching.md#6-deliberate-deviations-from-the-reference-spec-and-why).
2. **Backend needs a JDK 21 toolchain specifically**, even if a newer JDK is
   installed system-wide. Lombok 1.18.38 (latest release as of this build)
   silently fails to run its annotation processor under JDK 25 — no error,
   just missing getters/setters, which then fails compilation with confusing
   "cannot find symbol" errors. If `java -version` on your machine reports 25
   (or anything Lombok doesn't yet support), grab a JDK 21 and point
   `JAVA_HOME` at it before running Maven — see `backend/dev-env.sh` /
   `backend/dev-env.ps1`, which do exactly this against a portable JDK
   already unzipped under `.tools/` in this repo.

## Running everything

### Option A — Docker Compose (recommended if you have Docker)

```bash
docker compose -f docker/docker-compose.yml up --build
```

This starts Postgres (schema + seed data applied automatically), the AI
service, the backend, and the frontend. Open **http://localhost:8080**.

### Option B — Native (no Docker), what this project was actually built against

**1. Database.** Any PostgreSQL 17 works; the commands below spin up an
isolated instance dedicated to this project so nothing on your machine's
existing Postgres install is touched (adjust the binary path for your
install):

```bash
# One-time: initialize a fresh cluster with a known app user
initdb -D database/pgdata -U innovategov -A trust

# Set the port to 5433 in database/pgdata/postgresql.conf if 5432 is taken

# Start it
pg_ctl -D database/pgdata -l database/pglogs/server.log start

# Create the database and apply schema + seed data
createdb -h 127.0.0.1 -p 5433 -U innovategov innovategov
psql -h 127.0.0.1 -p 5433 -U innovategov -d innovategov -f database/schema.sql
psql -h 127.0.0.1 -p 5433 -U innovategov -d innovategov -f database/seed.sql
```

**2. AI service** (Python 3.10/3.11 — avoid brand-new Python releases until
numpy/torch have published wheels for them):

```bash
cd ai-service
python -m venv .venv
./.venv/Scripts/activate        # Windows; `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
cp .env.example .env            # defaults already point at the local DB above
uvicorn app.main:app --host 127.0.0.1 --port 8081
```

Runs on **http://localhost:8081**.

**3. Backend** (needs JDK 21 — see above):

```bash
cd backend
source dev-env.sh   # or: . .\dev-env.ps1   (PowerShell)
mvn spring-boot:run
```

Runs on **http://localhost:8001**. (Note: port 8080 is already in use by
something else on this machine — a system Oracle listener — which is why
neither service defaults to 8080; override with `SERVER_PORT` if needed.)

**4. Frontend:**

```bash
cd frontend
npm install
npm run dev
```

Runs on **http://localhost:5173** (Vite falls back to 5174/5175/... if that
port is taken by another local project — the backend's CORS config already
allows a few fallback ports out of the box; see `CORS_ALLOWED_ORIGIN` in
`backend/.env.example` if you need to add another one).

## Demo accounts

All seeded with the same password for convenience:

| Role | Email | Password |
|---|---|---|
| Government | `government@demo.com` | `Demo@123` |
| Startup | `startup@demo.com` | `Demo@123` |
| Expert | `expert@demo.com` | `Demo@123` |
| Admin | `admin@demo.com` | `Demo@123` |

`startup@demo.com` is **RoadSense AI**, a computer-vision road-inspection
startup whose seeded profile (including a prior Pune Municipal Corporation
pothole-detection pilot) is specifically what makes it rank #1 when matched
against the seeded "AI-Based Pothole & Road Damage Detection System"
challenge — the AI scores are real and computed live, but the seed data was
deliberately written so a judge sees a clear, sensible, differentiated
ranking rather than every startup scoring ~90%.

## Judge demo script (~5-7 minutes)

1. **Login as Government.** See the seeded challenges list.
2. Open **"AI-Based Pothole & Road Damage Detection System"** — walk through
   its problem statement, KPIs, and eligibility requirements.
3. Click **"Find Suitable Startups"** — this is a live AI computation, not a
   canned response (watch the "AI is scoring every startup..." loading state).
4. Point out **RoadSense AI at #1** — open its score breakdown (semantic
   similarity, technology/domain match, experience, readiness) and read its
   "why this match" reasons and the one flagged gap (no demonstrated IoT
   Sensors capability).
5. Optionally, create a **new challenge** via "New Challenge" to show the
   Problem-to-Challenge Converter and the "similar past pilots" AI lookup.
6. **Login as Startup** (`startup@demo.com`) — show its profile and its
   already-submitted proposal for the pothole challenge.
7. **Login as Expert** — open the evaluation queue, show the AI-assisted
   analysis alongside the manual scoring rubric, submit an evaluation.
8. **Back as Government** — shortlist the proposal, create a pilot with
   milestones and KPI targets.
9. Open an already-**completed** pilot (seeded: CleanLoop Robotics / Digital
   Waste Segregation) to show the KPI tracking, the generated SCALE
   recommendation with its cost/performance/impact breakdown and rationale,
   and the recorded human final decision.
10. **Login as Admin** — show user management, audit logs, and the
    cross-department Knowledge Base of past pilots (1 scaled, 1 rejected in
    the seed data) with domain/technology/outcome search.

## Environment variables

See `.env.example` in each service directory (`backend/`, `ai-service/`,
`frontend/`). Every value has a working local-dev default, so nothing needs
to be set to run the app locally — the `.env.example` files exist to
document what *can* be overridden (and are required for a real deployment,
e.g. `JWT_SECRET`).

## Testing

```bash
# AI service — matching formula unit tests (15 tests)
cd ai-service && ./.venv/Scripts/python.exe -m pytest tests/ -v

# Backend — recommendation engine, evaluation scoring, validation, and a full
# RBAC/auth integration suite run against a real (seeded) database (32 tests)
cd backend && source dev-env.sh && mvn test
```

The backend's `AuthRbacIntegrationTest` boots the full Spring context against
the live local database rather than an in-memory substitute, because the
schema leans on native Postgres enum/array/jsonb types that an H2
compatibility mode doesn't faithfully emulate — so the dev database must be
running (as it would be for any other local development) for that suite to pass.

## Implemented features

- Full JWT auth + RBAC across 4 roles, enforced server-side (`@PreAuthorize`)
  and mirrored client-side (route guards)
- Problem-to-Challenge Converter: structured challenges with typed
  requirements and weighted KPIs, draft/publish lifecycle
- Startup profiles: capabilities, past projects (with government-client
  tracking), self-reported pilot readiness
- **Real AI matching**: embeddings (local sentence-transformers, LLM-provider
  option with automatic fallback), a documented weighted formula across 5
  components, persisted ranked results, and template-generated
  reasons/gaps explanations
- Proposal submission, rule-based document verification with automated
  flagging, RBAC-scoped document access
- Expert evaluation workflow with a weighted rubric and an AI-assisted
  analysis summary (explicitly labeled as an aid, not a replacement, for the
  expert's judgment)
- Shortlisting → pilot creation → milestone and KPI tracking with recorded
  history
- Deterministic Scale/Modify/Reject recommendation engine (cost/performance/impact
  scoring with documented, unit-tested decision boundaries) with a
  separately-recorded human final decision
- Searchable cross-department knowledge base of past pilots, plus an
  AI-similarity lookup surfaced while drafting a new challenge
- Notifications, audit logging of every state-changing action, admin user
  management
- Full test coverage of the two scoring engines (matching formula,
  recommendation engine) with fixed-input unit tests, plus a live RBAC/auth
  integration suite

## Known limitations & suggested next steps

- **No pgvector / ANN index** — see the engineering-decision note above; a
  drop-in upgrade path is documented in `docs/ai-matching.md`.
- **No expert-assignment table** — any expert can pick up any pending
  proposal from the shared queue, rather than proposals being routed to a
  specific assigned expert. Adding an `evaluation_assignments` table would be
  a small, additive schema change.
- **Cost-efficiency in the recommendation engine is a schedule-adherence
  proxy** (fraction of milestones completed without delay), not a real
  actual-vs-budgeted cost ledger — documented in `RecommendationCalculator`'s
  Javadoc. A future iteration could add per-milestone budgeted-vs-actual
  cost tracking.
- **Rate limiting is in-memory/per-instance** — fine for this single-instance
  deployment, would need Redis (or a gateway) for a multi-instance one.
- **Document verification is rule-based**, not an ML/OCR content classifier —
  a deliberate scope decision (see `docs/api.md`), since the spec's "AI-assisted
  verification" is satisfied by real, explainable automated checks without
  overreaching into a model that wasn't asked for.
- **LLM provider path is implemented but untested against a real key** in
  this environment (no key was available) — the local fallback path is what
  was actually built and demoed against throughout, and is what the AI
  service defaults to.
