# ProcureFlow

Startup-friendly public procurement for government departments — a prototype for
**Smart India Hackathon 2026, problem statement SIH26136 (Government of Maharashtra)**.

Procurement is tiered by risk, so startups get real access where failure is containable. A
KPI-tracked pilot, validated by someone other than the supplier, replaces turnover and
prior-experience requirements as the proof that a young company can deliver.

> Every company, founder, challenge and pilot in this repository is **sample data** generated for
> the prototype. Scores produced by the platform are **prototype-generated** and are not official
> evaluation criteria.

## The Lifecycle

```
department posts a problem in plain language
  -> AI Problem Analyzer structures it and proposes measurable KPIs
  -> officer approves, KPIs lock
  -> tier engine classifies SMALL / MEDIUM / LARGE
  -> two-gate eligibility (formal existence & DPIIT/startup checks)
  -> semantic matching ranks startups with explainable sub-scores
  -> shortlist, or decline with a mandatory reason code
  -> pilot plan with milestones
  -> startup submits KPI evidence
  -> independent evaluator validates
  -> Scale / Modify / Reject recommendation
  -> officer decides
  -> outcome saved to a cross-department knowledge base
```

## Rules This Codebase Does Not Bend

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

## Architecture & Technology Stack

| Layer | Choice |
| :--- | :--- |
| **Backend** | Python 3.12, FastAPI, SQLAlchemy 2, Pydantic 2, Alembic, psycopg 3 |
| **Database** | Local PostgreSQL 13+ (no Docker, standard relational schema) |
| **Frontend** | React 19, TypeScript, Vite, Tailwind CSS v4, shadcn/ui, Recharts |
| **Embeddings & AI** | CPU cosine similarity, sentence-transformers fallback, deterministic LLM fallback |

The AI and matching logic runs in-process inside FastAPI. There is no second microservice to manage.

---

## Local Setup

### Prerequisites
- **Python 3.12**
- **Node.js 20+**
- **PostgreSQL 13 or newer** (running locally on port 5432)

### 1. Environment Configuration

```bash
# Copy template configuration
cp .env.example .env
cp web/.env.example web/.env
```

Edit `.env` to configure your PostgreSQL credentials in `DATABASE_URL`:
```env
DATABASE_URL=postgresql+psycopg://postgres:<your_password>@localhost:5432/procureflow
```

### 2. Backend Virtualenv Setup

```bash
# Windows
py -3.12 -m venv api/.venv
api/.venv/Scripts/python -m pip install -r api/requirements.txt

# macOS / Linux
python3.12 -m venv api/.venv
api/.venv/bin/pip install -r api/requirements.txt
```

### 3. Frontend Setup

```bash
npm install
npm run install:web
```

### 4. Database Setup & Migrations

```bash
# Apply migrations to head
npm run db:migrate

# Seed demo data
npm run db:seed

# Optional: To completely drop, recreate, migrate, and reseed clean demo state:
npm run db:reset
```

---

## Running the Application

To run both the FastAPI backend (`http://localhost:8000`) and the Vite web app (`http://localhost:5173`) concurrently:

```bash
npm run dev
```

- **Web Frontend**: <http://localhost:5173>
- **API Swagger Documentation**: <http://localhost:8000/docs>
- **Health Check**: <http://localhost:8000/health>

---

## Demo Accounts & Role Routes

All four demo accounts use the password configured in `DEMO_PASSWORD` in `.env` (default: `demo1234`).

| E-mail | Role | Landing Route | Description |
| :--- | :--- | :--- | :--- |
| `officer@mahagov.in` | `GOVERNMENT` | `/government` | Department dashboard: problem analyzer, KPI locking, tiering, barrier analysis, pilot decisions |
| `founder@startup.in` | `STARTUP` | `/startup` | Startup portal: browse open challenges, view explainable match sub-scores, submit proposals, report KPI evidence |
| `expert@evaluator.in` | `EXPERT` | `/evaluation` | Evaluation queue: claim proposals, mark rubrics, independently validate claimed KPIs |
| `admin@procureflow.in` | `ADMIN` | `/fairness` | Governance dashboard: founder-level rotation (multi-company founders), splitting detection, audit trails |

Additional accessible routes:
- `/admin/rules`: Live procurement threshold rules editor (Admin)
- `/partnerships`: Large-tier execution partnerships (Government / Admin)

---

## Testing & Quality Assurance

```bash
# Run all backend pytest test suites (Phase 1 through Phase 5)
npm test

# Run frontend production typecheck and build
npm run build --prefix web
```

---

## Repository Structure

```
├── .env.example          # Environment template (safe defaults)
├── package.json          # Root scripts (dev, test, db:migrate, db:seed, db:reset)
├── api/
│   ├── app/
│   │   ├── main.py       # FastAPI application & CORS setup
│   │   ├── config.py     # Pydantic BaseSettings
│   │   ├── db.py         # SQLAlchemy engine & session factory
│   │   ├── models.py     # Database schema models
│   │   ├── enums.py      # Domain enums
│   │   ├── deps.py       # Role-based access control (RBAC) dependencies
│   │   ├── routers/      # API endpoints (auth, admin, challenges, proposals, pilots, engine)
│   │   └── services/     # Domain services (analyzer, tiering, barriers, matching, rotation, splitting)
│   ├── alembic/          # Database migrations
│   ├── scripts/          # Seed and reset scripts (deterministic demo data)
│   └── tests/            # Pytest test suites
└── web/
    ├── src/
    │   ├── auth/         # AuthContext & token management
    │   ├── components/   # Layout, ThemeToggle, ThemeProvider, UI primitives
    │   ├── pages/        # GovernmentDashboard, StartupPortal, ExpertEvaluation, FairnessDashboard, etc.
    │   ├── lib/          # API fetch client & utilities
    │   └── types.ts      # TypeScript interfaces
    ├── package.json      # Frontend dependencies
    └── vite.config.ts    # Vite bundler configuration
```
