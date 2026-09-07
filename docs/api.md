# API Reference

Base path: `/api/v1`. All request/response bodies are JSON unless noted.
Authenticated endpoints expect `Authorization: Bearer <jwt>`, obtained from
`/auth/login`. Error responses share one shape (see **Error format** below).

Role names: `GOVERNMENT`, `STARTUP`, `EXPERT`, `ADMIN`. "Owner" below means
the `GOVERNMENT` account whose department owns the challenge in question, or
the `STARTUP` account that owns the resource — `ADMIN` can access anything.

## Error format

```json
{
  "timestamp": "2026-01-01T12:00:00Z",
  "status": 400,
  "error": "Bad Request",
  "message": "Add at least one eligibility/technical requirement before publishing",
  "path": "/api/v1/challenges/.../publish",
  "fieldErrors": { "email": "must be a well-formed email address" }
}
```

`fieldErrors` is only present for Bean Validation failures (400s from a
malformed request body).

---

## Auth (`/auth`)

| Method | Path | Auth | Roles | Body | Response | Status |
|---|---|---|---|---|---|---|
| POST | `/auth/register` | No | — (self-registers) | `{email, password, fullName, role: STARTUP\|GOVERNMENT, companyName?, departmentName?, ministry?, region?}` | `AuthResponse` (token, userId, email, fullName, role) | 201, 400, 409, 403 (if role is EXPERT/ADMIN) |
| POST | `/auth/login` | No | — | `{email, password}` | `AuthResponse` | 200, 401 |
| GET | `/auth/me` | Yes | any | — | `{id, email, fullName, role}` | 200, 401 |

`EXPERT` and `ADMIN` accounts cannot self-register — they're provisioned via
seed data / by an existing `ADMIN`. Auth endpoints are additionally rate
limited: 15 requests/minute per IP (`RateLimitFilter`), returning 429 with
`{"error":"RATE_LIMITED", ...}` past that.

## Challenges (`/challenges`)

| Method | Path | Auth | Roles | Body | Response | Status |
|---|---|---|---|---|---|---|
| POST | `/challenges` | Yes | GOVERNMENT | `ChallengeCreateRequest` (title, problemStatement, domain, desiredTechnology?, outcomesExpected?, budgetRange?, timelineDays?, requirements[], kpis[]) | `ChallengeResponse` | 201, 400 |
| PUT | `/challenges/{id}` | Yes | GOVERNMENT (owner) | same as create | `ChallengeResponse` | 200, 403, 404, 409 (not DRAFT) |
| POST | `/challenges/{id}/publish` | Yes | GOVERNMENT (owner) | — | `ChallengeResponse` (status → PUBLISHED) | 200, 400 (no requirements), 403, 409 |
| GET | `/challenges/{id}` | Yes | any | — | `ChallengeResponse` | 200, 404 (DRAFT hidden from non-owners) |
| GET | `/challenges` | Yes | any | — | `ChallengeResponse[]` — GOVERNMENT sees own department's (all statuses); STARTUP/EXPERT see PUBLISHED and later; ADMIN sees all | 200 |

Publishing auto-creates a default 4-criterion evaluation rubric if none
exists (Technical Feasibility 30%, Cost Effectiveness 25%, Scalability 25%,
Team Capability 20%) and triggers the AI service to compute the challenge's
embedding (best-effort — a failure here doesn't block publishing; matching
computes it lazily instead, see `docs/ai-matching.md`).

## Startups (`/startups`)

| Method | Path | Auth | Roles | Body | Response | Status |
|---|---|---|---|---|---|---|
| GET | `/startups/me` | Yes | STARTUP | — | `StartupResponse` | 200, 404 |
| PUT | `/startups/me` | Yes | STARTUP | `UpdateStartupProfileRequest` | `StartupResponse` | 200, 400 |
| POST | `/startups/me/capabilities` | Yes | STARTUP | `{technologyTag, domainTag, proficiencyLevel: 1-5, description?}` | `StartupResponse` | 200, 400 |
| DELETE | `/startups/me/capabilities/{capabilityId}` | Yes | STARTUP | — | — | 204 |
| POST | `/startups/me/projects` | Yes | STARTUP | `{title, domain, technologyStack?, clientType: GOVERNMENT\|PRIVATE, outcomeSummary?, year?}` | `StartupResponse` | 200, 400 |
| GET | `/startups` | Yes | GOVERNMENT, EXPERT, ADMIN | — | `StartupResponse[]` | 200 |
| GET | `/startups/{id}` | Yes | GOVERNMENT, EXPERT, ADMIN | — | `StartupResponse` | 200, 404 |

Every profile/capability/project mutation triggers a best-effort embedding
recomputation (see `docs/ai-matching.md`, §1).

## Matching (`/matching`) — the centerpiece

| Method | Path | Auth | Roles | Body | Response | Status |
|---|---|---|---|---|---|---|
| POST | `/matching/challenges/{challengeId}/run` | Yes | GOVERNMENT (owner), ADMIN | — | `AiMatchResponse` (challengeId, aiProvider, weights, totalCandidatesConsidered, results[]) | 200, 403, 404, 503 (AI service down) |
| GET | `/matching/challenges/{challengeId}` | Yes | GOVERNMENT (owner), ADMIN | — | `MatchResultDto[]` (persisted results from the last run) | 200, 403, 404 |

`run` performs a **real, synchronous** computation (see `docs/ai-matching.md`)
and persists the results before returning; it is not a mock and not cached
beyond what's already in `match_results`. If the AI service is unreachable,
the backend returns 503 rather than fabricating a score.

## Proposals (`/proposals`)

| Method | Path | Auth | Roles | Body | Response | Status |
|---|---|---|---|---|---|---|
| POST | `/proposals/challenges/{challengeId}` | Yes | STARTUP | `{summary, proposedApproach?, costEstimate?, timelineEstimateDays?}` | `ProposalResponse` | 201, 409 (already submitted, or challenge not accepting), 403 |
| GET | `/proposals/challenges/{challengeId}` | Yes | GOVERNMENT (owner), EXPERT, ADMIN | — | `ProposalResponse[]` | 200, 403, 404 |
| GET | `/proposals/{id}` | Yes | owner STARTUP, GOVERNMENT (owner), EXPERT, ADMIN | — | `ProposalResponse` | 200, 403, 404 |
| GET | `/proposals/mine` | Yes | STARTUP | — | `ProposalResponse[]` | 200 |
| GET | `/proposals/queue` | Yes | EXPERT | — | `ProposalResponse[]` (all SUBMITTED/UNDER_REVIEW proposals — see note below) | 200 |
| PATCH | `/proposals/{id}/status` | Yes | GOVERNMENT (owner), ADMIN | `{status: SHORTLISTED\|REJECTED\|UNDER_REVIEW\|SUBMITTED}` | `ProposalResponse` | 200, 403, 404 |

**On "assigned" proposals**: the schema has no separate expert-assignment
table, so the expert queue is "available to any expert" rather than routed to
a specific one — documented as a deliberate simplification in
`ProposalService`.

## Documents (`/documents`)

| Method | Path | Auth | Roles | Body | Response | Status |
|---|---|---|---|---|---|---|
| POST | `/documents/{ownerType}/{ownerId}` | Yes | owner (STARTUP for its own profile or its own proposal) | multipart/form-data: `file`, query param `documentType: ELIGIBILITY\|COMPLIANCE\|FINANCIAL\|OTHER` | `DocumentResponse` (includes automated `verificationStatus`) | 201, 400, 403 |
| GET | `/documents/{ownerType}/{ownerId}` | Yes | owner STARTUP, GOVERNMENT (if the owner has a proposal against its challenges), EXPERT, ADMIN | — | `DocumentResponse[]` | 200, 403 |

`ownerType` is `STARTUP` (owner = startup id) or `PROPOSAL` (owner = proposal
id). Verification is rule-based (file type/size checks), not an ML model —
see `docs/architecture.md` / `DocumentService`'s class Javadoc for why.

## Evaluations (`/evaluations`)

| Method | Path | Auth | Roles | Body | Response | Status |
|---|---|---|---|---|---|---|
| GET | `/evaluations/proposals/{proposalId}/criteria` | Yes | EXPERT, GOVERNMENT, ADMIN | — | `EvaluationCriterionDto[]` | 200, 404 |
| GET | `/evaluations/proposals/{proposalId}/ai-analysis` | Yes | EXPERT, GOVERNMENT, ADMIN | — | `{summary: string}` | 200, 404, 503 |
| POST | `/evaluations/proposals/{proposalId}` | Yes | EXPERT | `{comments?, scores: [{criterionId, score, remarks?}]}` | `EvaluationResponse` (includes computed `totalScore`) | 200, 400 (unknown criterion) |

Submitting an evaluation moves the proposal from `SUBMITTED` to
`UNDER_REVIEW` if it hadn't already been shortlisted/rejected, and snapshots
the AI-assist summary into the stored evaluation.

## Pilots (`/pilots`)

| Method | Path | Auth | Roles | Body | Response | Status |
|---|---|---|---|---|---|---|
| POST | `/pilots` | Yes | GOVERNMENT (owner of the challenge), ADMIN | `PilotCreateRequest` (challengeId, startupId, startDate, endDate?, milestones[], kpis[], contract?) | `PilotResponse` | 201, 403, 404 |
| GET | `/pilots/{id}` | Yes | GOVERNMENT (owner), STARTUP (own pilot), ADMIN | — | `PilotResponse` | 200, 403, 404 |
| GET | `/pilots` | Yes | any | — | `PilotResponse[]` — scoped to the caller (own department's / own startup's / all for ADMIN; EXPERT sees none) | 200 |
| PATCH | `/pilots/{id}/milestones/{milestoneId}` | Yes | GOVERNMENT (owner), ADMIN | `{status: PENDING\|IN_PROGRESS\|DONE\|DELAYED, completionDate?}` | `PilotResponse` | 200, 403, 404 |
| POST | `/pilots/{id}/kpis/{kpiId}/results` | Yes | GOVERNMENT (owner), ADMIN | `{recordedValue, notes?}` | `PilotResponse` | 200, 403, 404 |
| POST | `/pilots/{id}/complete` | Yes | GOVERNMENT (owner), ADMIN | `{finalStatus: COMPLETED\|TERMINATED}` | `PilotResponse` — also generates the recommendation | 200, 400, 403 |
| GET | `/pilots/{id}/recommendation` | Yes | any with pilot access | — | `RecommendationResponse` | 200, 404 (not generated yet) |
| POST | `/pilots/{id}/recommendation/decision` | Yes | GOVERNMENT (owner), ADMIN | `{finalDecision: SCALE\|MODIFY\|REJECT}` | `RecommendationResponse` (with `finalDecision`, `reviewedByName`, `decidedAt` set) | 200, 403, 404 |

Completing a pilot runs the deterministic Scale/Modify/Reject engine
(`RecommendationCalculator` — see `docs/architecture.md`) and creates/updates
the pilot's knowledge-base entry. Recording a final decision updates that
knowledge-base entry's `success` flag to reflect the human decision.

## Knowledge Base (`/knowledge-base`)

| Method | Path | Auth | Roles | Body | Response | Status |
|---|---|---|---|---|---|---|
| GET | `/knowledge-base?domain=&technology=&success=&q=` | Yes | any | — | `KnowledgeBaseEntryDto[]` | 200 |
| POST | `/knowledge-base/similar-for-draft` | Yes | GOVERNMENT, ADMIN | `{title, problemStatement, domain, desiredTechnology?, outcomesExpected?}` | `AiKnowledgeBaseSimilarResponse` (embedding-similarity search over past pilots) | 200, 503 |

## Notifications (`/notifications`)

| Method | Path | Auth | Roles | Body | Response | Status |
|---|---|---|---|---|---|---|
| GET | `/notifications` | Yes | any | — | `NotificationDto[]` (own, newest first) | 200 |
| GET | `/notifications/unread-count` | Yes | any | — | `{unread: number}` | 200 |
| PATCH | `/notifications/{id}/read` | Yes | any (owner) | — | — | 204, 403, 404 |

## Admin (`/admin`)

| Method | Path | Auth | Roles | Body | Response | Status |
|---|---|---|---|---|---|---|
| GET | `/admin/users` | Yes | ADMIN | — | `AdminUserDto[]` | 200 |
| PATCH | `/admin/users/{id}/active` | Yes | ADMIN | `{active: boolean}` | `AdminUserDto` | 200, 404 |
| GET | `/admin/audit-logs?page=&size=` | Yes | ADMIN | — | `Page<AuditLogDto>` (Spring `Page` shape: `content`, `totalElements`, `totalPages`, `number`, `size`) | 200 |

---

For interactive exploration, springdoc-openapi is on the classpath — run the
backend and visit `/swagger-ui.html` (or `/api-docs` for the raw OpenAPI JSON).
