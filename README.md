# ProcureFlow

Startup-friendly public procurement for government departments — a prototype for
**Smart India Hackathon 2026, problem statement SIH26136 (Government of Maharashtra)**.

Procurement is tiered by risk, so startups get real access where failure is containable. A
KPI-tracked pilot, validated by someone other than the supplier, replaces turnover and
prior-experience requirements as the proof that a young company can deliver.

> Every company, founder, challenge and pilot in this repository is **sample data** generated for
> the prototype. Scores produced by the platform are **prototype-generated** and are not official
> evaluation criteria.

## The lifecycle

```
department posts a problem in plain language
  -> AI Problem Analyzer structures it and proposes measurable KPIs
  -> officer approves, KPIs lock
  -> tier engine classifies SMALL / MEDIUM / LARGE
  -> two-gate eligibility
  -> semantic matching ranks startups with explainable sub-scores
  -> shortlist, or decline with a reason code
  -> pilot plan with milestones
  -> startup submits KPI evidence
  -> independent evaluator validates
  -> Scale / Modify / Reject recommendation
  -> officer decides
  -> outcome saved to a cross-department knowledge base
```

## Rules this codebase does not bend

1. **No threshold, percentage or limit is hard-coded.** Every one lives in `procurement_rule`
   (`rule_name`, `rule_type`, `value`, `active`, `source_reference`, `effective_from`).
2. **The AI never invents a constraint.** Budget, timeline and location come only from department
   input; anything absent goes to `missing_fields` and blocks publishing until an officer fills it.
3. **Eligibility is rule-based, never LLM-generated.** The LLM suggests capabilities and outcomes.
4. **A startup never validates its own KPIs.** `claimed_value` and `validated_value` are separate
   columns with `validated_by`.
5. **Every AI output is a recommendation** with a human approval step. Nothing is auto-awarded.
6. **All scores are explainable** — per-criterion sub-scores, each with a reason.
7. **Everything is audited**: classification, score, fallback trigger, approval and override, with
   actor, timestamp and reason.

A rule with an empty `source_reference` is a **prototype setting**, not a verified legal
requirement, and the UI says so.

## Stack

| Layer      | Choice                                                                   |
| ---------- | ------------------------------------------------------------------------ |
| Backend    | Python 3.12, FastAPI, SQLAlchemy 2, Pydantic 2, Alembic                   |
| Database   | Local PostgreSQL (no Docker, no pgvector)                                 |
| Frontend   | React + TypeScript + Vite + Tailwind v4 + shadcn/ui + Recharts            |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` on CPU, cosine similarity in Python |
| LLM        | One provider-agnostic module, key from env, deterministic template fallback |
| AI runtime | In-process inside FastAPI. `GET /ai-status` reports what is actually configured |

The AI runs in-process inside FastAPI. There is no second service to start.

## Local setup

**Prerequisites:** Python 3.12, Node 20+, and a running local PostgreSQL 13 or newer.

```bash
# 1. Environment
cp .env.example .env          # then edit DATABASE_URL for your PostgreSQL
cp web/.env.example web/.env  # optional; defaults to http://localhost:8000

# 2. Backend virtualenv (Windows paths shown; use .venv/bin on macOS and Linux)
py -3.12 -m venv api/.venv
api/.venv/Scripts/python -m pip install -r api/requirements.txt

# 3. Frontend
npm install
npm run install:web

# 4. Database: create it, migrate it, seed it
npm run db:reset
```

`npm run db:reset` drops the database, recreates it, runs every migration and reseeds. It is the
**demo reset button** — safe to run mid-presentation, and safe to run twice in a row.

## Commands

| Command              | What it does                                              |
| -------------------- | --------------------------------------------------------- |
| `npm run dev`        | Runs the API (port 8000) and the web app (port 5173) together |
| `npm run db:reset`   | Drops, recreates, migrates and reseeds the database         |
| `npm run db:migrate` | Runs Alembic migrations only                                |
| `npm run db:seed`    | Reseeds without dropping                                    |
| `npm test`           | Runs the backend test suite                                 |
| `npm run test:fresh` | Resets the database, then runs the tests                     |

API docs while it runs: <http://localhost:8000/docs>

## Demo accounts

All four share the password in `DEMO_PASSWORD` (default `demo1234`).

| E-mail                  | Role       | Belongs to                             |
| ----------------------- | ---------- | -------------------------------------- |
| `officer@mahagov.in`    | GOVERNMENT | Water Supply and Sanitation Department |
| `founder@startup.in`    | STARTUP    | AquaSense Analytics                    |
| `expert@evaluator.in`   | EXPERT     | —                                      |
| `admin@procureflow.in`  | ADMIN      | —                                      |

## What the seed contains

30 startups across Maharashtra districts with varied capability profiles, 10 legacy firms, 8
government departments, 4 founders who each appear on more than one company (which is what makes
founder-level rotation and the fairness dashboard meaningful), 8 completed past challenges with
pilots and validated KPI results, and the procurement rules the engines read.

## Repository layout

```
api/
  app/
    models.py        SQLAlchemy models for every table
    enums.py         the domain vocabulary (never thresholds)
    deps.py          server-side RBAC
    routers/         API endpoints
    services/        engines and shared services (audit, rules, AI)
  alembic/           migrations
  scripts/seed.py    deterministic demo data
  scripts/reset_db.py  drop, recreate, migrate, reseed
  tests/
web/
  src/auth/          session and role context
  src/components/    shadcn/ui primitives and RequireRole
  src/pages/         screens
```

## The engines

Every number these engines apply is read from `procurement_rule` at the moment it is needed. The
modules that decide tiers and eligibility contain **no numeric literals at all**, which the test
suite enforces by parsing their syntax trees.

**Tier engine.** The value picks a starting band from `SMALL_TENDER_LIMIT` and
`MEDIUM_TENDER_LIMIT`. HIGH criticality then moves the challenge up a tier, because a failure that
matters is not containable at its price. HIGH innovation potential moves it down a tier, because a
novel solution is worth piloting where failure stays contained. A floor guarantees that a
high-criticality challenge never lands in SMALL, whatever its value. The decision comes back with a
reason for each factor and the rules it cited.

**Two gates.** Gate 1 applies to every bidder and asks only whether it is a legally constituted
entity that has made a technical submission — no turnover floor, no experience requirement. Gate 2
is the startup lane: recognition, company age, size, and prior participation (reported, never
blocking). A large firm passes gate 1 and fails gate 2.

**Tier access.** SMALL is startups only. MEDIUM is startup-first and opens to large firms only when
the fallback trigger fires — too few qualified startup bids, or none above `MIN_TECH_SCORE`, once
`BID_WINDOW_DAYS` has elapsed — and the values that fired it go into the audit log. LARGE is open,
and carries the bidder's validated KPI history into scoring.

**Barrier analysis.** When an officer drafts a challenge, the engine flags proposed eligibility
criteria that shut startups out, says whether each is essential or merely traditional, and cites
what the platform applies instead. It flags; the officer decides. Nothing is blocked, and nothing
here is generated by an LLM.

## The five screens

Each role lands on its own screen and the server refuses the others.

| Screen | Role | What it does |
| ------ | ---- | ------------ |
| Department dashboard | GOVERNMENT | Post a problem, review the analyzer output and missing fields, read the tier explanation, run barrier analysis, see applicants with their sub-scores, track the pilot and record the final decision |
| Startup portal | STARTUP | Profile, browse and apply, submit KPI evidence, read its own score breakdown and any decline reason, milestone and payment status |
| Evaluation queue | EXPERT | Claim a proposal, read the AI-assisted summary beside the computed match, score a manual rubric |
| Partnership | GOVERNMENT, ADMIN | Solution Owner and Execution Partner side by side, with scopes, IP ownership and milestone status |
| Fairness and governance | ADMIN | Opportunities per founder group, partnerships per execution firm, startup participation against the target, tier distribution, and the full audit trail |

## Demo walkthrough

Reset first, so the demo starts from a known state:

```bash
npm run db:reset
npm run dev
```

Then, signing in as each demo account in turn:

1. **Officer** (`officer@mahagov.in`) — Department dashboard. Paste a problem in plain language
   and press **Analyze**. The knowledge base surfaces *"similar solution piloted before"* with the
   outcome, cost and lessons learned. The analyzer returns capabilities, outcomes and KPIs to
   measure — and reports `budget`, `timeline` and `location` as **missing**, because the AI never
   supplies them.
2. **Create draft**, then try **Publish**: refused, listing what is missing.
3. Fill in budget, timeline, district, criticality and innovation potential. The missing list
   clears.
4. **Approve and lock KPIs.** Approving a second time is refused: locked means locked.
5. **Publish.** The tier engine classifies the challenge and shows its reasoning, citing the rules
   it read and whether each is a prototype setting.
6. **Barrier analysis** flags which traditional criteria would exclude startups, and cites what
   the platform applies instead. It flags; you decide.
7. **Startup** (`founder@startup.in`) — My portal. Browse, apply. The proposal comes back with six
   sub-scores, each with a reason, and a note that proximity did not count because the challenge
   needs no on-site work.
8. **Expert** (`expert@evaluator.in`) — Evaluation queue. Claim the proposal, read the AI summary
   beside the computed match, score the rubric by hand.
9. **Officer** — award one bidder; decline another with a reason code (the form will not submit
   without one). The declined startup sees the code, the explanation and its own breakdown.
10. **Officer** — draft milestones from the locked KPIs, approve the plan, start the pilot.
11. **Startup** — submit KPI evidence. Trying to validate it is refused.
12. **Expert** — validate each KPI. `claimed_value` and `validated_value` stay separate.
13. **Recommendation** — computed from validated KPIs and schedule adherence, with direction
    respected, and it changes nothing: `outcome` stays empty until an officer decides.
14. **Officer decides.** Deciding against the recommendation is allowed and logged as an override.
15. **Admin** (`admin@procureflow.in`) — Fairness and governance. Participation, tier spread,
    opportunities per founder group (not per company), and the audit trail with every step above.

## Build status

All six phases are complete: schema and seed data, the rules engine with tiering and two-gate
eligibility, founder-level rotation and splitting detection, the problem analyzer and knowledge
base, matching, evaluation, pilots and partnerships, and the five role dashboards.
