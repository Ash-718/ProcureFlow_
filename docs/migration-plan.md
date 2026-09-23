# Migration Plan — Spring Boot ➜ Python FastAPI

**Status:** planning complete, implementation not yet started.
**Scope:** replace the Java backend with Python. Keep the product, the database,
the data, and the AI logic. Improve the React frontend substantially.

---

## 1. Decision summary

| | Before | After |
|---|---|---|
| Frontend | React 19 + TS + Vite + Tailwind v4 + Radix + Recharts | **Same stack**, significantly expanded and redesigned |
| Backend | Spring Boot 3.5 / Java 21 / JPA / Spring Security | **FastAPI + SQLAlchemy 2 + Pydantic v2** |
| AI | Separate FastAPI service on :8081, called over HTTP | **Merged into the backend** as `app/ai/` — same process, same session |
| Database | PostgreSQL 17 on :5433 | **Unchanged.** Same schema, same seed data, same port |
| Local dev | 4 processes (+ Docker option) | **3 processes**: Postgres, backend, frontend. No Docker |
| Deployment | docker-compose | Docker retained in `docker/`, for deployment only |

Two services collapse into one because the AI layer already talks to the same
PostgreSQL database through SQLAlchemy and returns plain dicts. Once the
backend is Python, the HTTP hop between them buys nothing and costs a process,
a port, a serialisation round-trip, and a whole class of "is the AI service
up?" failure modes during a demo.

---

## 2. Inventory of what exists

### 2.1 Java backend — 143 files

| Layer | Count | Detail |
|---|---|---|
| Controllers | 12 | 46 endpoints total (§4) |
| Entities | 25 + 14 enums | Maps 1:1 onto 26 tables in `database/schema.sql` |
| Repositories | 24 | Spring Data JPA interfaces |
| Services | 17 | Incl. `MatchingService`, `RecommendationCalculator`, `EvaluationScoring`, `AuditService`, `AiServiceClient` |
| DTOs | ~45 | Across 10 sub-packages |
| Security | 6 | `JwtService`, `JwtAuthenticationFilter`, `RateLimitFilter`, `AppUserDetailsService`, `CurrentUserService`, `AuthenticatedUser` |
| Config | 1 | `SecurityConfig` — CORS, stateless JWT, `@EnableMethodSecurity` |

### 2.2 Python AI service — 23 files, **all reusable**

`scoring.py`, `explanations.py`, `matching_service.py`, `embedding_service.py`,
`knowledge_base_service.py`, `proposal_analysis.py`, `text_builders.py`,
`embeddings.py`, `text_generation.py`.

Critically, these use **raw SQL via `sqlalchemy.text()`**, not ORM models. They
need only a `Session`. Merging them into the backend is a package move plus an
import rewrite — not a rewrite.

The `all-MiniLM-L6-v2` model is **already cached** in
`~/.cache/huggingface/hub`, so matching runs offline with no download.

### 2.3 Frontend — 47 source files

Present: `AppShell`, `RequireAuth`, `useAuth`, a shadcn-style UI kit
(button/card/badge/dialog/tabs/select/input/progress/skeleton/status-badge/
state-views), 15 pages, `api/client.ts` + `api/endpoints.ts`, and a complete
`types/index.ts`.

Absent, and needed: **role dashboards** (all four roles land on a list page,
not a dashboard), a government proposals view, an evaluations list, a
shortlist comparison view, and breadcrumbs.

### 2.4 Database — live and verified

Started locally on :5433 during this inspection. Row counts:

```
users 22 · startups 16 · challenges 6 · proposals 6
pilots 2 · pilot_knowledge_base 2 · match_results 8 · audit_logs 25
```

Demo scenario intact: **Pothole Detection Pilot — Pune Municipal Corporation**
with **RoadSense AI**. Logins `government@demo.com` / `startup@demo.com` /
`expert@demo.com` / `admin@demo.com`, password `Demo@123`, bcrypt `$2b$10$`.

**No schema change is required.** `schema.sql` and `seed.sql` stay as they are.

---

## 3. Target backend structure

```
backend/
├── app/
│   ├── main.py                 # FastAPI app, middleware, exception handlers, routers
│   ├── core/
│   │   ├── config.py           # pydantic-settings; reads the existing .env keys
│   │   ├── database.py         # engine, SessionLocal, get_db
│   │   └── logging.py
│   ├── models/                 # SQLAlchemy 2.0 mapped classes → existing tables
│   ├── schemas/                # Pydantic v2, camelCase aliases (§7)
│   ├── repositories/           # query layer
│   ├── services/               # ported business logic
│   │   ├── challenge_service.py     recommendation_service.py
│   │   ├── startup_service.py       evaluation_service.py
│   │   ├── proposal_service.py      pilot_service.py
│   │   ├── document_service.py      knowledge_base_service.py
│   │   ├── notification_service.py  audit_service.py
│   │   ├── admin_service.py         matching_service.py
│   │   ├── recommendation_calculator.py   # pure, unit-testable
│   │   └── evaluation_scoring.py          # pure, unit-testable
│   ├── security/
│   │   ├── jwt.py              # HS256, same claims as JwtService
│   │   ├── password.py         # bcrypt, verifies existing $2b$10$ hashes
│   │   ├── deps.py             # current_user, require_roles(...)
│   │   └── rate_limit.py       # port of RateLimitFilter
│   ├── ai/                     # ← ai-service/app/ moved here, imports rewritten
│   │   ├── embeddings.py       text_generation.py
│   │   ├── scoring.py          explanations.py       text_builders.py
│   │   ├── matching.py         embedding_service.py
│   │   ├── knowledge_base.py   proposal_analysis.py
│   ├── api/v1/                 # one router per former controller
│   └── utils/
├── alembic/                    # baseline = current schema; no destructive autogen
├── tests/
├── requirements.txt
└── .env.example
```

---

## 4. Endpoint mapping — all 46

Every path, method, response shape and role guard is preserved **exactly**, so
the frontend needs no API changes to keep working.

### Auth — `/api/v1/auth`
| Method | Path | Guard | Python target |
|---|---|---|---|
| POST | `/register` | public | `api/v1/auth.py` → `AuthService.register` |
| POST | `/login` | public | `AuthService.login` |
| GET | `/me` | authenticated | `deps.current_user` |

### Challenges — `/api/v1/challenges`
| Method | Path | Guard | Python target |
|---|---|---|---|
| POST | `` | GOVERNMENT | `ChallengeService.create` |
| PUT | `/{id}` | GOVERNMENT | `ChallengeService.update` |
| POST | `/{id}/publish` | GOVERNMENT | `publish` → seeds default rubric, triggers embedding |
| GET | `/{id}` | authenticated | `get` |
| GET | `` | authenticated | `list` (role-scoped) |

### Startups — `/api/v1/startups`
| Method | Path | Guard |
|---|---|---|
| GET | `/me` | STARTUP |
| PUT | `/me` | STARTUP |
| POST | `/me/capabilities` | STARTUP |
| DELETE | `/me/capabilities/{capabilityId}` | STARTUP |
| POST | `/me/projects` | STARTUP |
| GET | `` | GOVERNMENT, EXPERT, ADMIN |
| GET | `/{startupId}` | GOVERNMENT, EXPERT, ADMIN |

### Matching — `/api/v1/matching`
| Method | Path | Guard | Note |
|---|---|---|---|
| POST | `/challenges/{challengeId}/run` | GOVERNMENT, ADMIN | **Direct call into `app.ai.matching`** instead of HTTP to :8081 |
| GET | `/challenges/{challengeId}` | GOVERNMENT, ADMIN | reads `match_results` |

### Proposals — `/api/v1/proposals`
| Method | Path | Guard |
|---|---|---|
| POST | `/challenges/{challengeId}` | STARTUP |
| GET | `/challenges/{challengeId}` | GOVERNMENT, EXPERT, ADMIN |
| GET | `/{id}` | authenticated (ownership-checked) |
| GET | `/mine` | STARTUP |
| GET | `/queue` | EXPERT |
| PATCH | `/{id}/status` | GOVERNMENT, ADMIN |

### Documents — `/api/v1/documents`
| Method | Path | Guard | Note |
|---|---|---|---|
| POST | `/{ownerType}/{ownerId}` | authenticated | multipart; `UploadFile` → `FILE_STORAGE_PATH` |
| GET | `/{ownerType}/{ownerId}` | authenticated | access control in service, not DB |

### Evaluations — `/api/v1/evaluations`
| Method | Path | Guard |
|---|---|---|
| GET | `/proposals/{proposalId}/criteria` | EXPERT, GOVERNMENT, ADMIN |
| GET | `/proposals/{proposalId}/ai-analysis` | EXPERT, GOVERNMENT, ADMIN |
| POST | `/proposals/{proposalId}` | EXPERT |

### Pilots — `/api/v1/pilots`
| Method | Path | Guard |
|---|---|---|
| POST | `` | GOVERNMENT, ADMIN |
| GET | `/{id}` | authenticated |
| GET | `` | authenticated (role-scoped) |
| PATCH | `/{id}/milestones/{milestoneId}` | GOVERNMENT, ADMIN |
| POST | `/{id}/kpis/{kpiId}/results` | GOVERNMENT, ADMIN |
| POST | `/{id}/complete` | GOVERNMENT, ADMIN |
| GET | `/{id}/recommendation` | authenticated |
| POST | `/{id}/recommendation/decision` | GOVERNMENT, ADMIN |

### Knowledge base — `/api/v1/knowledge-base`
| Method | Path | Guard |
|---|---|---|
| GET | `` | authenticated |
| POST | `/similar-for-draft` | GOVERNMENT, ADMIN |

### Notifications — `/api/v1/notifications`
| Method | Path | Guard |
|---|---|---|
| GET | `` | authenticated |
| GET | `/unread-count` | authenticated |
| PATCH | `/{id}/read` | authenticated |

### Admin — `/api/v1/admin`
| Method | Path | Guard |
|---|---|---|
| GET | `/users` | ADMIN |
| PATCH | `/users/{id}/active` | ADMIN |
| GET | `/audit-logs` | ADMIN — returns Spring-shaped `Page<T>` |

### Root
`GET /` and `GET /health` — public.

### Internal AI (no longer HTTP; called in-process)
`embed_challenge`, `embed_startup`, `embed_kb_entry`, `run_matching`,
`analyze_proposal`, `similar_past_pilots`.

---

## 5. Entity mapping

25 JPA entities → 25 SQLAlchemy models against the **same 26 tables**. UUID PKs
via `gen_random_uuid()`, `postgresql.UUID(as_uuid=True)`.

`roles · users · government_departments · startups · startup_capabilities ·
startup_projects · challenges · challenge_requirements · challenge_kpis ·
match_results · proposals · documents · evaluation_criteria · evaluations ·
evaluation_scores · contracts · pilots · pilot_milestones · payments · kpis ·
kpi_results · recommendations · pilot_knowledge_base · notifications ·
audit_logs · ai_matching_config`

Type notes that will bite if missed:

- **14 native PG enums** (`role_name`, `challenge_status`, …) → `sqlalchemy.Enum`
  with `native_enum=True` and matching names; **not** `String`.
- `challenges.embedding` / `startups.embedding` → `ARRAY(Float)` (`double
  precision[]`). No pgvector, per the existing documented decision.
- `pilot_knowledge_base.technology_tags` → `ARRAY(Text)`, GIN-indexed.
- `match_results.explanation_json` → `JSONB`.
- `pilot_knowledge_base.success` is **tri-state** (`true`/`false`/`null`) — must
  stay `bool | None`, never coerced to `False`.
- Money/scores are `NUMERIC` → `Decimal`, serialised as JSON numbers.

---

## 6. Auth and RBAC mapping

| Spring | Python |
|---|---|
| `BCryptPasswordEncoder` | `bcrypt` — verifies the existing `$2b$10$` hashes unchanged, so **seeded logins keep working** |
| `JwtService` HS256, `sub`=userId, claims `email`+`role`, 86 400 000 ms | `PyJWT`, identical claims and TTL, same `JWT_SECRET` (incl. the short-secret zero-padding to 32 bytes, or the tokens differ) |
| `JwtAuthenticationFilter` | `get_current_user` dependency |
| `@PreAuthorize("hasRole('X')")` | `Depends(require_roles("X"))` |
| `RateLimitFilter` | ASGI middleware, same window/limit |
| CORS from `CORS_ALLOWED_ORIGIN` (comma-separated) | `CORSMiddleware`, same parsing |
| `ErrorResponse` | Exception handlers producing the identical body (§7) |

---

## 7. Frontend contract constraints — the migration's real risk

The frontend is typed against Jackson's output. Three things must match or the
UI breaks silently:

1. **camelCase JSON.** Every response key is camelCase (`fullName`,
   `problemStatement`, `semanticSimilarityScore`). Pydantic emits snake_case by
   default. Every schema gets:
   ```python
   model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
   ```
   and every response is serialised `by_alias=True`.

2. **Error body.** `apiErrorMessage()` reads `error.response.data.message`.
   Handlers must emit:
   ```json
   {"timestamp","status","error","message","path","fieldErrors"?}
   ```

3. **Spring `Page<T>`.** `/admin/audit-logs` must return
   `{content, totalElements, totalPages, number, size}` — zero-based `number`.

A contract test asserts every response against `frontend/src/types/index.ts`.

**Port change:** Spring ran on 8001. FastAPI runs on **8000**, so
`frontend/vite.config.ts` proxy target changes `8001 → 8000`. This is the only
frontend change required for the backend swap itself.

---

## 8. Local development — no Docker

```powershell
# 1. PostgreSQL (already initialised in database/pgdata)
& "C:\Program Files\PostgreSQL\17\bin\pg_ctl" -D ".\database\pgdata" -o "-p 5433" -l ".\database\pglogs\server.log" start

# 2. Backend
cd backend; .\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000

# 3. Frontend
cd frontend; npm run dev
```

Docker stays in `docker/` for deployment and is documented separately. It is
never required for development or the SIH demo.

---

## 9. Phased execution, with a verification gate on each phase

| Phase | Work | Gate |
|---|---|---|
| 1 | Scaffold, config, DB session, SQLAlchemy models | Every model round-trips against the live seeded DB |
| 2 | Security: bcrypt, JWT, deps, rate limit | `Demo@123` verifies against a seeded hash; token matches Spring's shape |
| 3 | Schemas + error handlers + `Page<T>` | Contract test vs `types/index.ts` |
| 4 | Auth, Challenge, Startup routers | Frontend login + challenge list works against Python |
| 5 | Move `ai-service/app` → `backend/app/ai`, rewrite imports | `test_scoring.py` passes unchanged; matching returns real ranked results |
| 6 | Matching, Proposal, Document routers | RoadSense AI ranks #1 on the pothole challenge |
| 7 | Evaluation, Pilot, Recommendation, KB, Notification, Admin | All 46 endpoints answer |
| 8 | Full backend + AI + RBAC test suite | Green |
| 9 | **Frontend runs entirely on Python backend; every page verified** | **Gate for deletion** |
| 10 | Delete `backend/src`, `pom.xml`, `.tools/jdk-*`, `ai-service/`; update compose | Repo has no Java |
| 11 | Design system + app shell + role dashboards + all page polish | Demo flow at 1366×768 / 1440×900 / 1920×1080 |
| 12 | Docs: README rewrite, local-dev vs Docker split | — |

Phases 1–8 add files only. **Nothing is deleted before phase 10**, and phase 10
is gated on phase 9 passing.

---

## 10. Deletion criteria for the Java backend

`backend/src/main/java`, `backend/pom.xml`, `backend/dev-env.*`,
`.tools/jdk-21.0.12.1+1/`, `.github/modernize/java-upgrade/` and `ai-service/`
are removed only once **all** of these hold:

- All 46 endpoints implemented and returning contract-identical JSON.
- All four seeded roles log in and reach their landing pages.
- AI matching produces real ranked results from the live pipeline.
- Recommendation engine reproduces the Java calculator's numbers on the seeded
  pilots (verified by a port-parity test with fixed inputs).
- Audit logging writes on the same actions.
- `npm run build` clean; no console errors on any route.

---

## 11. Risks

| Risk | Mitigation |
|---|---|
| Silent camelCase mismatch breaks a page with no error | Contract test generated from `types/index.ts`; verify every page in phase 9 |
| JWT secret padding differs → seeded sessions rejected | Port the zero-pad-to-32-bytes behaviour verbatim |
| PG enum handling → `invalid input value for enum` | `native_enum=True` with explicit type names; asserted in phase 1 |
| `Decimal` vs float drift in recommendation scores | Port-parity test against the Java calculator's outputs |
| Deleting Java too early loses migration reference | Hard gate at phase 9; Java is the source of truth until then |
| Scope creep in the frontend redesign delays a working backend | Backend correct and green (phases 1–10) before redesign (phase 11) |
