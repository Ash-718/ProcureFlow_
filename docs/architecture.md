# Architecture

## System overview

```
┌─────────────────┐        ┌────────────────────────────────────┐
│                 │  REST  │        FastAPI backend             │
│  React frontend │───────▶│  business logic, auth/RBAC,        │
│  (Vite, TS,     │◀───────│  REST API, and the AI matching     │
│  Tailwind)      │  JSON  │  pipeline (app/ai/) in-process     │
└─────────────────┘        └─────────────────┬──────────────────┘
                                             │ SQLAlchemy
                                             ▼
                            ┌────────────────────────────────────┐
                            │            PostgreSQL              │
                            │  schema owned by database/*.sql    │
                            └────────────────────────────────────┘
```

One backend process. The matching pipeline — embeddings, cosine similarity,
the weighted formula, explanations, and persisting `match_results` — runs
inside it, sharing the same SQLAlchemy session as the request that triggered
it.

## Why one service rather than two

This started as Spring Boot plus a separate FastAPI AI service, with the two
communicating over HTTP and both connecting to the same schema. The backend
was migrated to Python, at which point that split stopped paying for itself:

- the AI code already talked to PostgreSQL through SQLAlchemy and returned
  plain dictionaries, so once the caller was also Python the HTTP hop bought
  nothing;
- it cost a process, a port, a serialisation round-trip, and an "is the AI
  service up?" failure mode during a demo;
- the two-service arrangement existed to bridge Java and Python. With no Java,
  there is nothing to bridge.

The migration moved the AI modules verbatim — `scoring.py` and
`text_builders.py` are byte-identical to their originals, and the rest differ
only in import paths. The weighted formula, the `all-MiniLM-L6-v2` embeddings
and the deterministic template explanations are unchanged. See
[`migration-plan.md`](migration-plan.md).

## Request flow: the centerpiece feature end-to-end

1. Government user clicks **"Find Suitable Startups"** on a published
   challenge (frontend: `gov-challenge-detail-page.tsx`).
2. Frontend calls `POST /api/v1/matching/challenges/{id}/run` (backend).
3. `app/api/v1/matching.py` → `MatchingService.run_matching` checks the caller
   owns the challenge's department (or is ADMIN), then calls
   `app.ai.run_matching_for_challenge` directly — an in-process function call
   on the request's own SQLAlchemy session, not a network hop.
4. `app/ai/matching.py` fetches the challenge, computes its embedding if
   missing, then for every startup: computes/loads its embedding, runs the
   five component scores (`scoring.py`), builds an explanation
   (`explanations.py`), and persists ranked rows into `match_results`.
5. The response (ranked candidates, scores, reasons/gaps, `ai_provider`) is
   serialised by `MatchResponse`, whose Pydantic aliases emit camelCase for
   the frontend.
6. Frontend renders the ranked list with a score gauge, per-component bars,
   and the reasons/gaps as bullet lists (`match-candidate-card.tsx`).
7. A subsequent page load reads the same data back via
   `GET /api/v1/matching/challenges/{id}`, which the backend serves directly
   from the `match_results` table (`MatchResultRow`) — no recomputation just
   to redisplay a result that was already computed and stored.

## Frontend structure

```
frontend/src/
├── api/          axios client (JWT interceptor) + one function per backend endpoint
├── types/        TypeScript interfaces mirroring backend DTOs
├── hooks/        useAuth (JWT session context)
├── components/
│   ├── ui/       small hand-built component library (button, card, badge,
│   │             dialog, select, tabs, progress, skeleton, state views) —
│   │             styled with Tailwind, patterned after shadcn/ui conventions
│   └── layout/   sidebar shell, route guards, per-role nav config, notification bell
└── pages/        one folder per role (government/startup/expert/admin) + shared
```

Route guards (`RequireAuth`) check both "is logged in" and "has an allowed
role" client-side; the backend enforces the same rules server-side via
`require_roles(...)` dependencies — the frontend check is a UX nicety (redirect instead of a
flash of a 403 page), never the actual security boundary.

## Backend structure

```
backend/app/
├── main.py         FastAPI app: middleware, exception handlers, router mount
├── core/           settings, SQLAlchemy engine/session, error handling
├── models/         SQLAlchemy 2.0 models mapped onto the existing schema
├── schemas/        Pydantic v2 request/response models (camelCase on the wire)
├── repositories/   query layer, one module per aggregate
├── services/       business logic + RBAC checks
├── security/       JWT issue/verify, bcrypt, auth dependencies, rate limiting
├── ai/             the matching pipeline (see below)
├── api/v1/         routers, one per resource
└── utils/          logging helpers
```

Roughly the layering the previous Java backend used, expressed in FastAPI
idiom: routers are thin and delegate to services, services own the
transaction boundary and the authorisation rules, repositories hold the SQL.

**Authorisation.** `@PreAuthorize` becomes a `require_roles(...)` dependency;
ownership rules (does this department own this challenge?) live in the
services, as they did before. Two behaviours are worth stating because they
are load-bearing:

- A **role mismatch returns 403, never 401.** The frontend clears the session
  on any 401, so returning 401 here would silently sign a user out whenever
  they opened a page their role simply cannot see.
- A **draft challenge belonging to another department returns 404, not 403** —
  its existence is itself confidential.

**Deferred embedding refresh.** Publishing a challenge or editing a startup
profile queues a best-effort embedding recompute. It runs *after* the
transaction commits, never inside it: the embedding code re-reads the row, and
under READ COMMITTED it would not see an uncommitted write. If the refresh
fails, the row keeps a NULL embedding and the matching pipeline computes it on
its next run — a missing embedding is recoverable, a wrong one would silently
corrupt every future score.

## AI module structure

```
backend/app/ai/
├── embeddings.py         EmbeddingProvider (local sentence-transformers / LLM)
├── text_generation.py    TextGenerationProvider (template / LLM polish)
├── text_builders.py      what actually gets embedded — plain, inspectable
├── scoring.py            the five component scores + weighted formula
├── explanations.py       deterministic reasons/gaps from those scores
├── embedding_service.py  compute + persist embeddings
├── matching.py           the pipeline: embed, score, rank, persist
├── knowledge_base.py     similarity search over past pilots
└── proposal_analysis.py  the AI aid shown to an expert
```

`scoring.py` is intentionally free of any DB or network dependency so the
matching formula's math is directly unit-testable with fixed inputs
(`backend/tests/test_scoring_migrated.py`, carried over unchanged from the
former AI service) — see `docs/ai-matching.md` for the formula itself.

## Deployment

Two supported paths, documented in the top-level `README.md`:

1. **Docker Compose** (`docker/docker-compose.yml`): plain `postgres:17-alpine`
   (see `docs/ai-matching.md` for why not a pgvector image) with schema +
   seed auto-applied via `/docker-entrypoint-initdb.d`, plus the two
   services. This is the path a judge with Docker available should use.
2. **Local/native** (what this project is actually built and demoed against,
   since the development environment has no Docker): a dedicated local
   PostgreSQL cluster (`database/pgdata`, isolated from any system-wide
   Postgres install), `uvicorn` for the backend, and the Vite dev server for
   the frontend. Three processes, no containers, no JVM.

## Future scalability notes

- **pgvector**: swap the `double precision[]` embedding columns for native
  `vector(384)` columns with an `ivfflat`/`hnsw` index once a build
  environment with Docker or a working C toolchain is available — the
  application code change is limited to the embedding storage/query layer in
  `backend/app/ai/`.
- **Async matching**: for a much larger startup database, `run_matching_for_challenge`
  should move from a synchronous request/response to a background job with
  polling/websocket status, since it currently scores every startup in the
  database on every run.
- **Read replicas / connection pool sizing**: the AI service and backend
  share one Postgres instance; a production deployment would want
  independent connection pool tuning (and likely a read replica for the
  AI service's read-heavy matching queries) once concurrent usage grows
  beyond a demo/prototype scale.
- **Rate limiting**: `RateLimitFilter` is a simple in-memory per-IP fixed
  window, appropriate for a single-instance deployment; a multi-instance
  deployment would move this to Redis or an API gateway.
