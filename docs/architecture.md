# Architecture

## System overview

```
┌─────────────────┐        ┌──────────────────────┐        ┌───────────────────────┐
│                 │  REST  │                      │  REST  │                       │
│  React frontend │───────▶│  Spring Boot backend │───────▶│  FastAPI AI service   │
│  (Vite, TS,     │◀───────│  (business logic,    │◀───────│  (embeddings,         │
│  Tailwind)      │  JSON  │   auth/RBAC, REST API)│  JSON  │   weighted matching,  │
│                 │        │                      │        │   explanations)       │
└─────────────────┘        └──────────┬───────────┘        └───────────┬───────────┘
                                       │                                │
                                       │         JDBC / SQLAlchemy      │
                                       ▼                                ▼
                            ┌────────────────────────────────────────────┐
                            │              PostgreSQL                    │
                            │  (owned/migrated by backend; both services │
                            │   read/write directly — see below)         │
                            └────────────────────────────────────────────┘
```

**Why the AI service talks to Postgres directly** rather than only through
the backend: the matching pipeline's heavy lifting — reading/writing
embeddings, computing cosine similarity, persisting `match_results` — is
naturally a database-adjacent operation, and Section 5 of the build spec
explicitly describes the AI service running the similarity query itself.
Routing every startup/challenge row through the backend as JSON just to hand
it to the AI service would add latency and complexity with no benefit; both
services connecting to one shared schema is standard for this "specialized ML
sidecar" pattern and is far simpler than either splitting the schema or
building a data-sync layer. The backend remains the schema owner (`database/schema.sql`
is applied once, up front; both services just read/write existing tables) and
the sole point of truth for authentication/authorization — the AI service is
never exposed directly to the frontend and has no concept of users or roles.

## Why this split (Spring Boot + FastAPI, not just one or the other)

- **Spring Boot** is the natural fit for the bulk of this system: relational
  data with real invariants (roles, ownership, one-proposal-per-startup,
  contract/payment records), RBAC enforced at the method level, and a large
  REST surface. Section 16 of the build spec also states this directly: "Spring
  Boot is the main backend; Python/FastAPI is AI-only."
- **FastAPI/Python** exists specifically because the embedding model
  (`sentence-transformers`) and the numpy-based scoring math belong in
  Python's ML ecosystem, not reimplemented in Java. Keeping it a thin,
  focused service (embeddings + matching + explanations + one analysis
  endpoint) rather than a second general-purpose backend avoids the
  "unnecessary microservices" trap the spec warns against — it does exactly
  one job.

## Request flow: the centerpiece feature end-to-end

1. Government user clicks **"Find Suitable Startups"** on a published
   challenge (frontend: `gov-challenge-detail-page.tsx`).
2. Frontend calls `POST /api/v1/matching/challenges/{id}/run` (backend).
3. `MatchingController` → `MatchingService.runMatching` checks the caller
   owns the challenge's department (or is ADMIN), then calls
   `AiServiceClient.runMatching`, a real synchronous HTTP call to
   `POST {AI_SERVICE_URL}/api/v1/ai/match/{id}`.
4. `ai-service`'s `matching_service.py` fetches the challenge, computes its
   embedding if missing, then for every startup: computes/loads its
   embedding, runs the five component scores (`scoring.py`), builds an
   explanation (`explanations.py`), and persists ranked rows into
   `match_results`.
5. The response (ranked candidates, scores, reasons/gaps, `ai_provider`)
   flows back through the backend to the frontend unchanged in shape (see
   `AiMatchResponse` — note the `@JsonAlias` usage there specifically so this
   pass-through DTO serializes as camelCase to the frontend while still
   deserializing ai-service's snake_case on the way in).
6. Frontend renders the ranked list with a score gauge, per-component bars,
   and the reasons/gaps as bullet lists (`match-candidate-card.tsx`).
7. A subsequent page load reads the same data back via
   `GET /api/v1/matching/challenges/{id}`, which the backend serves directly
   from its own `match_results` table (`MatchResultDto`) — no repeated
   AI-service round trip just to redisplay a result that was already computed
   and stored.

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
`@PreAuthorize` — the frontend check is a UX nicety (redirect instead of a
flash of a 403 page), never the actual security boundary.

## Backend structure

```
backend/src/main/java/com/innovategov/backend/
├── entity/       JPA entities (24), enums in entity/enums
├── repository/   Spring Data JPA repositories, one per entity
├── dto/          request/response DTOs, grouped by feature
├── service/      business logic + RBAC checks
├── controller/   thin REST controllers (@PreAuthorize, delegate to services)
├── security/     JWT issuing/parsing, Spring Security wiring, current-user helper
├── config/       SecurityConfig (CORS, filter chain)
├── exception/    ApiException + @RestControllerAdvice global handler
└── util/         AfterCommitRunner (see below)
```

**A note on `AfterCommitRunner`**: several service methods trigger a
best-effort AI-service call right after saving a row (e.g. "recompute this
startup's embedding after a profile save"). Firing that HTTP call *inside*
the still-open database transaction is a real bug, not a style choice — the
AI service, using its own separate database connection, queries under READ
COMMITTED isolation and won't see the just-saved row until the transaction
commits, so an eager trigger fired mid-transaction reliably 404s. `AfterCommitRunner`
defers the callback via `TransactionSynchronizationManager` so it only runs
once the transaction has actually committed. (This is exactly the kind of
bug the AI service's lazy on-demand embedding computation was already
resilient to — matching still worked throughout — but the eager path is what
Section 5 describes, so it's worth having correct too.)

## AI service structure

```
ai-service/app/
├── core/         config, embeddings (EmbeddingProvider), text_generation
│                 (TextGenerationProvider), db (SQLAlchemy engine)
├── services/     text_builders, scoring (pure functions, unit-tested),
│                 explanations, embedding_service, matching_service,
│                 proposal_analysis, knowledge_base_service
├── schemas/      Pydantic request/response models
├── routers/      matching.py, health.py
└── main.py       FastAPI app, CORS, global exception handler, provider warm-up
```

`scoring.py` is intentionally free of any DB/HTTP dependency so the matching
formula's math is directly unit-testable with fixed inputs
(`ai-service/tests/test_scoring.py`) — see `docs/ai-matching.md` for the
formula itself.

## Deployment

Two supported paths, documented in the top-level `README.md`:

1. **Docker Compose** (`docker/docker-compose.yml`): plain `postgres:17-alpine`
   (see `docs/ai-matching.md` for why not a pgvector image) with schema +
   seed auto-applied via `/docker-entrypoint-initdb.d`, plus the three
   services. This is the path a judge with Docker available should use.
2. **Local/native** (what this project was actually built and demoed
   against, since the development environment had neither Docker nor a
   working MSVC toolchain): a dedicated local PostgreSQL cluster
   (`database/pgdata`, isolated from any system-wide Postgres install),
   Maven/`spring-boot:run` for the backend (requires a JDK 21 toolchain — see
   `backend/dev-env.sh`/`.ps1` and the note below), and `uvicorn` for the AI
   service.

**A JDK version note worth flagging for anyone continuing this project**: the
backend must be built with **JDK 21**, not whatever newer JDK might be
installed system-wide. Lombok 1.18.38 (the latest release as of this build)
does not yet support annotation processing under JDK 25 — it silently
no-ops instead of erroring, so getters/setters/constructors never get
generated and compilation fails with confusing "cannot find symbol" errors
that look unrelated to Lombok. `backend/dev-env.sh` (bash) and
`backend/dev-env.ps1` (PowerShell) point `JAVA_HOME` at a portable JDK 21
already unzipped under `.tools/` for exactly this reason — source them before
running any `mvn` command.

## Future scalability notes

- **pgvector**: swap the `double precision[]` embedding columns for native
  `vector(384)` columns with an `ivfflat`/`hnsw` index once a build
  environment with Docker or a working C toolchain is available — the
  application code change is limited to the embedding storage/query layer in
  `ai-service`.
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
