# Migration Inventory — Spring Boot ➜ FastAPI

Produced in Phase 1. This is the reference every later phase works from: what
exists in Java, what replaces it in Python, and what the frontend requires of
both. The Java backend remains the authority until Phase 10.

---

## 1. Endpoint inventory — 46 endpoints, 12 controllers

Status legend: ☐ not started · ◐ in progress · ☑ ported and verified

| # | Method | Path | Role guard | Java source | Python target | Phase | Status |
|---|---|---|---|---|---|---|---|
| 1 | POST | `/api/v1/auth/register` | public | `AuthController` | `api/v1/auth.py` | 4 | ☐ |
| 2 | POST | `/api/v1/auth/login` | public | `AuthController` | `api/v1/auth.py` | 4 | ☐ |
| 3 | GET | `/api/v1/auth/me` | any | `AuthController` | `api/v1/auth.py` | 4 | ☐ |
| 4 | POST | `/api/v1/challenges` | GOVERNMENT | `ChallengeController` | `api/v1/challenges.py` | 4 | ☐ |
| 5 | PUT | `/api/v1/challenges/{id}` | GOVERNMENT | `ChallengeController` | `api/v1/challenges.py` | 4 | ☐ |
| 6 | POST | `/api/v1/challenges/{id}/publish` | GOVERNMENT | `ChallengeController` | `api/v1/challenges.py` | 4 | ☐ |
| 7 | GET | `/api/v1/challenges/{id}` | any | `ChallengeController` | `api/v1/challenges.py` | 4 | ☐ |
| 8 | GET | `/api/v1/challenges` | any | `ChallengeController` | `api/v1/challenges.py` | 4 | ☐ |
| 9 | GET | `/api/v1/startups/me` | STARTUP | `StartupController` | `api/v1/startups.py` | 4 | ☐ |
| 10 | PUT | `/api/v1/startups/me` | STARTUP | `StartupController` | `api/v1/startups.py` | 4 | ☐ |
| 11 | POST | `/api/v1/startups/me/capabilities` | STARTUP | `StartupController` | `api/v1/startups.py` | 4 | ☐ |
| 12 | DELETE | `/api/v1/startups/me/capabilities/{capabilityId}` | STARTUP | `StartupController` | `api/v1/startups.py` | 4 | ☐ |
| 13 | POST | `/api/v1/startups/me/projects` | STARTUP | `StartupController` | `api/v1/startups.py` | 4 | ☐ |
| 14 | GET | `/api/v1/startups` | GOV/EXPERT/ADMIN | `StartupController` | `api/v1/startups.py` | 4 | ☐ |
| 15 | GET | `/api/v1/startups/{startupId}` | GOV/EXPERT/ADMIN | `StartupController` | `api/v1/startups.py` | 4 | ☐ |
| 16 | POST | `/api/v1/matching/challenges/{id}/run` | GOV/ADMIN | `MatchingController` | `api/v1/matching.py` | 6 | ☐ |
| 17 | GET | `/api/v1/matching/challenges/{id}` | GOV/ADMIN | `MatchingController` | `api/v1/matching.py` | 6 | ☐ |
| 18 | POST | `/api/v1/proposals/challenges/{challengeId}` | STARTUP | `ProposalController` | `api/v1/proposals.py` | 6 | ☐ |
| 19 | GET | `/api/v1/proposals/challenges/{challengeId}` | GOV/EXPERT/ADMIN | `ProposalController` | `api/v1/proposals.py` | 6 | ☐ |
| 20 | GET | `/api/v1/proposals/{id}` | any (ownership) | `ProposalController` | `api/v1/proposals.py` | 6 | ☐ |
| 21 | GET | `/api/v1/proposals/mine` | STARTUP | `ProposalController` | `api/v1/proposals.py` | 6 | ☐ |
| 22 | GET | `/api/v1/proposals/queue` | EXPERT | `ProposalController` | `api/v1/proposals.py` | 6 | ☐ |
| 23 | PATCH | `/api/v1/proposals/{id}/status` | GOV/ADMIN | `ProposalController` | `api/v1/proposals.py` | 6 | ☐ |
| 24 | POST | `/api/v1/documents/{ownerType}/{ownerId}` | any (service-checked) | `DocumentController` | `api/v1/documents.py` | 6 | ☐ |
| 25 | GET | `/api/v1/documents/{ownerType}/{ownerId}` | any (service-checked) | `DocumentController` | `api/v1/documents.py` | 6 | ☐ |
| 26 | GET | `/api/v1/evaluations/proposals/{id}/criteria` | EXPERT/GOV/ADMIN | `EvaluationController` | `api/v1/evaluations.py` | 7 | ☐ |
| 27 | GET | `/api/v1/evaluations/proposals/{id}/ai-analysis` | EXPERT/GOV/ADMIN | `EvaluationController` | `api/v1/evaluations.py` | 7 | ☐ |
| 28 | POST | `/api/v1/evaluations/proposals/{id}` | EXPERT | `EvaluationController` | `api/v1/evaluations.py` | 7 | ☐ |
| 29 | POST | `/api/v1/pilots` | GOV/ADMIN | `PilotController` | `api/v1/pilots.py` | 7 | ☐ |
| 30 | GET | `/api/v1/pilots/{id}` | any | `PilotController` | `api/v1/pilots.py` | 7 | ☐ |
| 31 | GET | `/api/v1/pilots` | any (role-scoped) | `PilotController` | `api/v1/pilots.py` | 7 | ☐ |
| 32 | PATCH | `/api/v1/pilots/{id}/milestones/{milestoneId}` | GOV/ADMIN | `PilotController` | `api/v1/pilots.py` | 7 | ☐ |
| 33 | POST | `/api/v1/pilots/{id}/kpis/{kpiId}/results` | GOV/ADMIN | `PilotController` | `api/v1/pilots.py` | 7 | ☐ |
| 34 | POST | `/api/v1/pilots/{id}/complete` | GOV/ADMIN | `PilotController` | `api/v1/pilots.py` | 7 | ☐ |
| 35 | GET | `/api/v1/pilots/{id}/recommendation` | any | `PilotController` | `api/v1/pilots.py` | 7 | ☐ |
| 36 | POST | `/api/v1/pilots/{id}/recommendation/decision` | GOV/ADMIN | `PilotController` | `api/v1/pilots.py` | 7 | ☐ |
| 37 | GET | `/api/v1/knowledge-base` | any | `KnowledgeBaseController` | `api/v1/knowledge_base.py` | 7 | ☐ |
| 38 | POST | `/api/v1/knowledge-base/similar-for-draft` | GOV/ADMIN | `KnowledgeBaseController` | `api/v1/knowledge_base.py` | 7 | ☐ |
| 39 | GET | `/api/v1/notifications` | any | `NotificationController` | `api/v1/notifications.py` | 7 | ☐ |
| 40 | GET | `/api/v1/notifications/unread-count` | any | `NotificationController` | `api/v1/notifications.py` | 7 | ☐ |
| 41 | PATCH | `/api/v1/notifications/{id}/read` | any | `NotificationController` | `api/v1/notifications.py` | 7 | ☐ |
| 42 | GET | `/api/v1/admin/users` | ADMIN | `AdminController` | `api/v1/admin.py` | 7 | ☐ |
| 43 | PATCH | `/api/v1/admin/users/{id}/active` | ADMIN | `AdminController` | `api/v1/admin.py` | 7 | ☐ |
| 44 | GET | `/api/v1/admin/audit-logs` | ADMIN | `AdminController` | `api/v1/admin.py` | 7 | ☐ |
| 45 | GET | `/` | public | `RootController` | `app/main.py` | **1** | **☑** |
| 46 | GET | `/health` | public | `RootController` | `app/main.py` | **1** | **☑** |

### Internal AI operations — no longer HTTP

The former `ai-service` on :8081 exposed six endpoints that only the Spring
backend called, through `AiServiceClient`. After the merge these become
in-process function calls; `AiServiceClient` is deleted rather than ported.

| Former endpoint | Becomes | Called by |
|---|---|---|
| `POST /api/v1/ai/embeddings/challenge/{id}` | `ai.embedding_service.compute_and_store_challenge_embedding` | challenge publish |
| `POST /api/v1/ai/embeddings/startup/{id}` | `ai.embedding_service.compute_and_store_startup_embedding` | profile update, matching |
| `POST /api/v1/ai/embeddings/knowledge-base/{id}` | `ai.embedding_service.compute_and_store_kb_embedding` | KB entry write |
| `POST /api/v1/ai/match/{challenge_id}` | `ai.matching.run_matching_for_challenge` | endpoint 16 |
| `GET /api/v1/ai/analysis/proposal/{id}` | `ai.proposal_analysis.generate_proposal_analysis` | endpoint 27 |
| `POST /api/v1/ai/knowledge-base/similar` | `ai.knowledge_base.find_similar_pilots_for_challenge` | endpoint 38 |

---

## 2. Entity inventory — 25 entities ➜ 25 models ☑ **complete**

All mapped in Phase 1 and verified against the live database.

| Java entity | Table | Python model | Notable types |
|---|---|---|---|
| `Role` | `roles` | `models/identity.py` | enum `role_name` |
| `User` | `users` | `models/identity.py` | bcrypt hash, FK RESTRICT |
| `GovernmentDepartment` | `government_departments` | `models/identity.py` | 1:1 with user |
| `Startup` | `startups` | `models/startup.py` | `NUMERIC(5,2)`, `float8[]` embedding |
| `StartupCapability` | `startup_capabilities` | `models/startup.py` | CHECK 1–5 |
| `StartupProject` | `startup_projects` | `models/startup.py` | enum `client_type` |
| `Challenge` | `challenges` | `models/challenge.py` | enum `challenge_status`, `float8[]` |
| `ChallengeRequirement` | `challenge_requirements` | `models/challenge.py` | `is_mandatory` ➜ API `mandatory` |
| `ChallengeKpi` | `challenge_kpis` | `models/challenge.py` | `NUMERIC(14,2)` |
| `MatchResult` | `match_results` | `models/matching.py` | 6 × `NUMERIC(6,3)`, JSONB |
| — | `ai_matching_config` | `models/matching.py` | seeded weights |
| `Proposal` | `proposals` | `models/proposal.py` | UNIQUE(challenge, startup) |
| `Document` | `documents` | `models/proposal.py` | polymorphic owner, no FK |
| `EvaluationCriterion` | `evaluation_criteria` | `models/evaluation.py` | |
| `Evaluation` | `evaluations` | `models/evaluation.py` | AI summary snapshot |
| `EvaluationScore` | `evaluation_scores` | `models/evaluation.py` | UNIQUE(eval, criterion) |
| `Contract` | `contracts` | `models/pilot.py` | enum `contract_status` |
| `Pilot` | `pilots` | `models/pilot.py` | nullable contract |
| `PilotMilestone` | `pilot_milestones` | `models/pilot.py` | enum `milestone_status` |
| `Payment` | `payments` | `models/pilot.py` | nullable milestone |
| `Kpi` | `kpis` | `models/pilot.py` | `latest_result` helper |
| `KpiResult` | `kpi_results` | `models/pilot.py` | **append-only** |
| `Recommendation` | `recommendations` | `models/pilot.py` | generated vs. human columns |
| `PilotKnowledgeBase` | `pilot_knowledge_base` | `models/knowledge_base.py` | `text[]` GIN, **tri-state** `success` |
| `Notification` | `notifications` | `models/system.py` | `is_read` ➜ API `read` |
| `AuditLog` | `audit_logs` | `models/system.py` | JSONB metadata |

**14 native PostgreSQL enum types** are bound via `pg_enum()` with
`create_type=False`; all members verified identical to the database.

---

## 3. Service inventory — 17 services

| Java service | Lines | Python target | Phase | Notes |
|---|---|---|---|---|
| `AuthService` | 105 | `services/auth_service.py` | 4 | register, login, JWT issue |
| `ChallengeService` | 205 | `services/challenge_service.py` | 4 | publish seeds a default 4-criterion rubric |
| `StartupService` | 134 | `services/startup_service.py` | 4 | profile, capabilities, projects |
| `MatchingService` | 81 | `services/matching_service.py` | 6 | calls `app.ai` directly, not HTTP |
| `AiServiceClient` | 110 | **deleted** | 5 | replaced by in-process calls |
| `ProposalService` | 133 | `services/proposal_service.py` | 6 | |
| `DocumentService` | 148 | `services/document_service.py` | 6 | **all access control lives here** |
| `FileStorageService` | 47 | `services/file_storage.py` | 6 | writes under `FILE_STORAGE_PATH` |
| `EvaluationService` | 113 | `services/evaluation_service.py` | 7 | |
| `EvaluationScoring` | 30 | `services/evaluation_scoring.py` | 7 | pure — port-parity tested |
| `PilotService` | 209 | `services/pilot_service.py` | 7 | milestones, KPI results |
| `RecommendationCalculator` | 120 | `services/recommendation_calculator.py` | 7 | pure — **port-parity tested** |
| `RecommendationService` | 183 | `services/recommendation_service.py` | 7 | writes KB entry |
| `KnowledgeBaseService` | 45 | `services/knowledge_base_service.py` | 7 | |
| `NotificationService` | 46 | `services/notification_service.py` | 7 | |
| `AdminService` | 47 | `services/admin_service.py` | 7 | |
| `AuditService` | 35 | `services/audit_service.py` | 4 | needed early — every mutation writes one |

### Audit actions to preserve

`REGISTER · LOGIN · CREATE · UPDATE · PUBLISH · RUN_MATCHING · SUBMIT ·
STATUS_CHANGE · UPLOAD · UPDATE_PROFILE · SUBMIT_EVALUATION · UPDATE_MILESTONE ·
RECORD_KPI_RESULT · COMPLETE_PILOT · FINAL_DECISION · SCALE · MODIFY · REJECT ·
ACTIVATE_USER · DEACTIVATE_USER`

---

## 4. Recommendation engine — logic that must port exactly

`RecommendationCalculator` is pure and dependency-free, and its numbers are
visible in the demo, so it gets a port-parity test with fixed inputs.

| Element | Value |
|---|---|
| `SCALE_THRESHOLD` | `0.70` |
| `MODIFY_THRESHOLD` | `0.40` |
| `overall` | mean of cost, performance, impact |
| `performance_score` | mean per-KPI achievement ratio, each capped at 1.0 |
| `impact_score` | fraction of KPIs meeting or exceeding target |
| `cost_score` | fraction of milestones not `DELAYED`; `0.5` when there are none |
| lower-is-better keywords | `time`, `delay`, `latency`, `rate` |
| higher-is-better overrides | `reduction`, `increase`, `gain`, `improvement` |

Uses `Decimal`, not float. Division uses 4–6 dp with `ROUND_HALF_UP`.

## 5. Matching formula — preserved as-is

```
overall = 0.35·semantic + 0.20·technology + 0.15·domain
        + 0.15·experience + 0.15·readiness      (all 0–100)
```

`ai-service/app/services/scoring.py` and `explanations.py` move to
`backend/app/ai/` **unchanged apart from import paths**. `tests/test_scoring.py`
must pass without edits — that is the Phase 5 gate.

Component rules that must not drift: technology match credits proficiency/5 with
substring tag matching and scores `0.5` when a challenge names no technology;
domain match gives proficiency/5 via capability, `0.4` via past project, else 0;
experience gives ≤0.6 for up to 3 same-domain projects, +0.3 for same-domain
government work (+0.1 for other-domain government), +≤0.1 general.

---

## 6. Frontend contract — 47 files, treated as fixed

`frontend/src/types/index.ts` (334 lines) is the authority. Every response must
match it exactly.

| Requirement | Detail |
|---|---|
| **camelCase keys** | `fullName`, `problemStatement`, `semanticSimilarityScore`, … |
| **Column renames** | `is_mandatory`➜`mandatory`, `is_read`➜`read`, `is_active`➜`active` |
| **Error body** | `{timestamp, status, error, message, path, fieldErrors?}` — `apiErrorMessage()` reads `.message` |
| **Pagination** | `/admin/audit-logs` ➜ `{content, totalElements, totalPages, number, size}`, zero-based `number` |
| **Auth storage** | `localStorage["innovategov_token"]`, `Authorization: Bearer` |
| **401 handling** | any 401 outside `/auth/login` clears the token and redirects to `/login` |
| **Base URL** | `/api/v1` via the Vite proxy |
| **Derived fields** | `Challenge.departmentName`, `Proposal.challengeTitle`/`companyName`, `Evaluation.expertName`, `Recommendation.reviewedByName`, `AuditLogItem.actorEmail`, `PilotKpiItem.latestRecordedValue`/`latestRecordedAt` — all joined, not columns |

**Pages present:** 15. **Absent and needed in Phase 11:** dashboards for all four
roles, a government proposals view, an evaluations list, a shortlist comparison
view, breadcrumbs. Every role currently lands on a list page.

---

## 7. Coexistence during migration

| Process | Port | Owner | Until |
|---|---|---|---|
| PostgreSQL 17 | 5433 | shared | permanent |
| Spring Boot backend | 8001 | Java | Phase 10 |
| ai-service | 8081 | Python | Phase 5 |
| **FastAPI backend** | **8000** | Python | permanent |
| Vite dev server | 5173 | React | permanent |

The Vite proxy points at 8001 today and moves to 8000 in Phase 4, which is the
switch-over point. Until then the working application is unaffected.
