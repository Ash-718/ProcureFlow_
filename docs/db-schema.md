# Database Schema

Full DDL: [`database/schema.sql`](../database/schema.sql). Seed data:
[`database/seed.sql`](../database/seed.sql). PostgreSQL, UUID primary keys
(`gen_random_uuid()` via `pgcrypto`), `created_at`/timestamps on every table,
enums for lifecycle/status fields.

## Entity groups and relationships

```
roles ──< users ──< government_departments (1:1 per GOVERNMENT user)
                 └─< startups (1:1 per STARTUP user)
                        ├─< startup_capabilities
                        └─< startup_projects

government_departments ──< challenges ──< challenge_requirements
                                       ├─< challenge_kpis
                                       ├─< evaluation_criteria
                                       └─< match_results >── startups

challenges ──< proposals >── startups
                 └─< evaluations >── users (expert)
                        └─< evaluation_scores >── evaluation_criteria

challenges ──< pilots >── startups
                 ├── contracts (0..1, via pilots.contract_id)
                 │      └─< payments >── pilot_milestones (0..1)
                 ├─< pilot_milestones
                 ├─< kpis ──< kpi_results
                 ├── recommendations (1:1)
                 └── pilot_knowledge_base (1:1)

documents (polymorphic: owner_type/owner_id → STARTUP|PROPOSAL)
notifications >── users
audit_logs >── users (actor, nullable)
ai_matching_config (standalone config table, read by the backend)
```

## Table-by-table notes

### Identity & RBAC
- **roles**: the 4 fixed roles (`GOVERNMENT`, `STARTUP`, `EXPERT`, `ADMIN`), seeded once.
- **users**: one row per login. `role_id` is `ON DELETE RESTRICT` — a role in
  use can't be deleted out from under its users.
- **government_departments** / **startups**: exactly one per `GOVERNMENT` /
  `STARTUP` user (`user_id` is `UNIQUE`). `ON DELETE CASCADE` from `users` —
  deleting a user's account removes their department/startup profile with it.

### Startups
- **startup_capabilities**: `(technology_tag, domain_tag, proficiency_level
  1-5)` — the direct inputs to the AI matching engine's technology/domain
  match scores (see `docs/ai-matching.md`).
- **startup_projects**: past delivery history, including `client_type`
  (`GOVERNMENT`/`PRIVATE`) — the single strongest signal in the experience
  score.

### Challenges
- **challenges.embedding**: `double precision[]`, computed by the AI service
  on publish (see `docs/ai-matching.md` for why this isn't a native
  `vector` column).
- **challenge_requirements**: typed (`ELIGIBILITY`/`TECHNICAL`/`COMPLIANCE`),
  `is_mandatory` flag.
- **challenge_kpis**: measurable targets defined at challenge-creation time;
  copied into a pilot's own `kpis` rows when a pilot is created from a
  shortlisted proposal (a pilot can adjust targets without mutating the
  original challenge's KPI definitions).

### Matching
- **match_results**: one row per (challenge, startup) pair considered in the
  most recent matching run for that challenge — the table is cleared and
  reinserted on every re-run (`DELETE ... WHERE challenge_id = ?` then
  bulk-insert), so it always reflects the latest computation, not a history
  of every run. `explanation_json` (`jsonb`) holds the reasons/gaps/component
  breakdown. `UNIQUE (challenge_id, startup_id)`.

### Proposals & documents
- **proposals**: `UNIQUE (challenge_id, startup_id)` — one proposal per
  startup per challenge. `ON DELETE RESTRICT` on both FKs: a proposal is a
  financial/audit-relevant record and shouldn't silently disappear if a
  challenge or startup row is ever deleted.
- **documents**: polymorphic ownership (`owner_type` + `owner_id`, no FK
  constraint on `owner_id` since it can point at either `startups` or
  `proposals`) — access control for this table is enforced entirely in
  `DocumentService` (Section 14 of the build spec), not the database.

### Evaluation
- **evaluation_criteria**: per-challenge rubric; `ChallengeService` seeds a
  default 4-criterion rubric (Technical Feasibility 30%, Cost Effectiveness
  25%, Scalability 25%, Team Capability 20%) on publish if none exists yet.
- **evaluations** / **evaluation_scores**: `UNIQUE (proposal_id, expert_id)`
  and `UNIQUE (evaluation_id, criterion_id)` respectively — one evaluation
  per expert per proposal, one score per criterion per evaluation.
  `ai_assist_summary` stores a snapshot of the AI-generated analysis text at
  submission time (not a live pointer — the expert's record reflects what
  they actually saw).

### Pilots, contracts, payments
- **pilots**: `contract_id` is nullable and `ON DELETE SET NULL` — a pilot
  can exist (and even complete) without a formal contract row, matching how
  the seed data models pilots with informally-tracked value vs. ones with a
  full contract.
- **pilot_milestones**, **kpis** / **kpi_results**: `kpi_results` is
  append-only (every recorded measurement kept, not overwritten) so a pilot's
  KPI history is auditable; `PilotService`/`RecommendationService` always
  read the *latest* result per KPI.
- **payments**: `milestone_id` nullable — a payment can be tied to a specific
  milestone (typical) or be a flat disbursement.

### Recommendations & knowledge base
- **recommendations**: `UNIQUE (pilot_id)` — one recommendation per pilot,
  regenerated (upserted) if a pilot's KPIs/milestones change before final
  decision. `recommendation` (AI-generated) and `final_decision` (human,
  nullable until decided) are deliberately separate columns — the schema
  itself enforces the "AI assists, human decides" principle from Section 12.
- **pilot_knowledge_base**: `UNIQUE (pilot_id)` — created/updated when a
  recommendation is (re)generated or a final decision is recorded;
  `technology_tags` is a native Postgres `text[]` (GIN-indexed) for fast
  tag-overlap search; `success` is nullable (`true` = final decision SCALE,
  `false` = REJECT, `null` = MODIFY/undecided — a true tri-state, not a
  boolean pretending to be one).

### Notifications & audit
- **notifications**: simple per-user feed, `is_read` flag, no delete —
  read-state is tracked, history isn't pruned.
- **audit_logs**: `actor_user_id` is nullable and `ON DELETE SET NULL` — an
  audit trail entry must outlive the user who caused it, even if that
  account is later removed. `metadata_json` (`jsonb`) holds action-specific
  context (e.g. `{"newStatus": "SHORTLISTED"}`).

### AI config
- **ai_matching_config**: `(config_key, weight, description)` rows mirroring
  the weights in `backend/app/core/config.py` — kept here so the *documented*
  default weights are visible directly in the database, independent of
  whichever environment variables happen to override them at runtime.

## Indexing

Every foreign key has a supporting index. Additional indexes: `challenges.status`,
`challenges.domain`, `proposals.status`, `match_results(challenge_id, rank)`,
`documents(owner_type, owner_id)`, `documents.verification_status`,
`notifications(user_id, is_read)`, `audit_logs.created_at`,
`pilot_knowledge_base.domain` / `.department_id` / `.success`, and a GIN index
on `pilot_knowledge_base.technology_tags` for tag search.
