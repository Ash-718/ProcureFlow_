-- =====================================================================================
-- INNOVATE-GOV — Core Schema (PostgreSQL)
-- SIH26136 — AI-powered innovation procurement platform
--
-- NOTE ON VECTOR SIMILARITY (engineering decision):
-- The reference spec calls for pgvector + ivfflat indexes. This dev/demo environment
-- has no Docker and no MSVC build toolchain available to compile the pgvector
-- extension from source, and no pre-built Windows binary exists for it. Rather than
-- block the whole build on that, embeddings are stored as plain `double precision[]`
-- arrays and cosine similarity is computed in the AI service (numpy — real, exact,
-- reproducible computation, not an approximation). At the seeded scale (tens of
-- startups/challenges) brute-force cosine similarity is effectively instant, so the
-- only thing sacrificed vs. pgvector is the ANN index, which only matters at a much
-- larger scale. Swapping this column to `vector(384)` + an ivfflat index later is a
-- drop-in change if pgvector becomes available (see docs/ai-matching.md).
-- =====================================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto; -- gen_random_uuid()

-- =====================================================================================
-- ENUM TYPES
-- =====================================================================================
CREATE TYPE role_name AS ENUM ('GOVERNMENT', 'STARTUP', 'EXPERT', 'ADMIN');
CREATE TYPE challenge_status AS ENUM ('DRAFT', 'PUBLISHED', 'MATCHING', 'SHORTLISTED', 'PILOT', 'CLOSED');
CREATE TYPE requirement_type AS ENUM ('ELIGIBILITY', 'TECHNICAL', 'COMPLIANCE');
CREATE TYPE proposal_status AS ENUM ('SUBMITTED', 'UNDER_REVIEW', 'SHORTLISTED', 'REJECTED');
CREATE TYPE document_owner_type AS ENUM ('STARTUP', 'PROPOSAL');
CREATE TYPE document_type AS ENUM ('ELIGIBILITY', 'COMPLIANCE', 'FINANCIAL', 'OTHER');
CREATE TYPE verification_status AS ENUM ('PENDING', 'VERIFIED', 'FLAGGED');
CREATE TYPE pilot_status AS ENUM ('ACTIVE', 'COMPLETED', 'TERMINATED');
CREATE TYPE milestone_status AS ENUM ('PENDING', 'IN_PROGRESS', 'DONE', 'DELAYED');
CREATE TYPE contract_status AS ENUM ('DRAFT', 'ACTIVE', 'COMPLETED', 'TERMINATED');
CREATE TYPE payment_status AS ENUM ('PENDING', 'RELEASED', 'HELD');
CREATE TYPE recommendation_type AS ENUM ('SCALE', 'MODIFY', 'REJECT');
CREATE TYPE client_type AS ENUM ('GOVERNMENT', 'PRIVATE');
CREATE TYPE notification_type AS ENUM (
  'MATCH_READY', 'PROPOSAL_SUBMITTED', 'PROPOSAL_STATUS_CHANGE', 'DOCUMENT_VERIFIED',
  'DOCUMENT_FLAGGED', 'EVALUATION_ASSIGNED', 'EVALUATION_SUBMITTED', 'SHORTLISTED',
  'PILOT_CREATED', 'MILESTONE_DUE', 'MILESTONE_UPDATED', 'RECOMMENDATION_READY', 'GENERAL'
);

-- =====================================================================================
-- 1. IDENTITY & RBAC
-- =====================================================================================
CREATE TABLE roles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name role_name NOT NULL UNIQUE,
  description TEXT
);

CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(255) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  full_name VARCHAR(255) NOT NULL,
  role_id UUID NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_users_role_id ON users(role_id);

CREATE TABLE government_departments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
  department_name VARCHAR(255) NOT NULL,
  ministry VARCHAR(255),
  region VARCHAR(255),
  contact_designation VARCHAR(255),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_gov_dept_user_id ON government_departments(user_id);

-- =====================================================================================
-- 2. STARTUPS
-- =====================================================================================
CREATE TABLE startups (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
  company_name VARCHAR(255) NOT NULL,
  dpiit_number VARCHAR(100),
  founded_year INT,
  team_size INT,
  city VARCHAR(120),
  state VARCHAR(120),
  readiness_score NUMERIC(5,2) NOT NULL DEFAULT 50.00, -- 0-100
  description TEXT,
  embedding DOUBLE PRECISION[],
  embedding_model VARCHAR(100),
  embedding_updated_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_startups_user_id ON startups(user_id);

CREATE TABLE startup_capabilities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  startup_id UUID NOT NULL REFERENCES startups(id) ON DELETE CASCADE,
  technology_tag VARCHAR(120) NOT NULL,
  domain_tag VARCHAR(120) NOT NULL,
  proficiency_level INT NOT NULL DEFAULT 3 CHECK (proficiency_level BETWEEN 1 AND 5),
  description TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_startup_capabilities_startup_id ON startup_capabilities(startup_id);
CREATE INDEX idx_startup_capabilities_tech ON startup_capabilities(technology_tag);
CREATE INDEX idx_startup_capabilities_domain ON startup_capabilities(domain_tag);

CREATE TABLE startup_projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  startup_id UUID NOT NULL REFERENCES startups(id) ON DELETE CASCADE,
  title VARCHAR(255) NOT NULL,
  domain VARCHAR(120) NOT NULL,
  technology_stack VARCHAR(255),
  client_type client_type NOT NULL DEFAULT 'PRIVATE',
  outcome_summary TEXT,
  year INT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_startup_projects_startup_id ON startup_projects(startup_id);

-- =====================================================================================
-- 3. CHALLENGES
-- =====================================================================================
CREATE TABLE challenges (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  department_id UUID NOT NULL REFERENCES government_departments(id) ON DELETE RESTRICT,
  title VARCHAR(255) NOT NULL,
  problem_statement TEXT NOT NULL,
  desired_technology VARCHAR(255),
  domain VARCHAR(120) NOT NULL,
  outcomes_expected TEXT,
  budget_range VARCHAR(120),
  timeline_days INT,
  status challenge_status NOT NULL DEFAULT 'DRAFT',
  embedding DOUBLE PRECISION[],
  embedding_model VARCHAR(100),
  embedding_updated_at TIMESTAMPTZ,
  published_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_challenges_department_id ON challenges(department_id);
CREATE INDEX idx_challenges_status ON challenges(status);
CREATE INDEX idx_challenges_domain ON challenges(domain);

CREATE TABLE challenge_requirements (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  challenge_id UUID NOT NULL REFERENCES challenges(id) ON DELETE CASCADE,
  requirement_type requirement_type NOT NULL,
  description TEXT NOT NULL,
  is_mandatory BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE INDEX idx_challenge_requirements_challenge_id ON challenge_requirements(challenge_id);

CREATE TABLE challenge_kpis (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  challenge_id UUID NOT NULL REFERENCES challenges(id) ON DELETE CASCADE,
  kpi_name VARCHAR(255) NOT NULL,
  target_value NUMERIC(14,2),
  unit VARCHAR(60),
  weight NUMERIC(5,2) NOT NULL DEFAULT 1.00
);
CREATE INDEX idx_challenge_kpis_challenge_id ON challenge_kpis(challenge_id);

-- =====================================================================================
-- 4. MATCHING
-- =====================================================================================
CREATE TABLE match_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  challenge_id UUID NOT NULL REFERENCES challenges(id) ON DELETE CASCADE,
  startup_id UUID NOT NULL REFERENCES startups(id) ON DELETE CASCADE,
  overall_score NUMERIC(6,3) NOT NULL,
  semantic_similarity_score NUMERIC(6,3) NOT NULL,
  technology_match_score NUMERIC(6,3) NOT NULL,
  domain_match_score NUMERIC(6,3) NOT NULL,
  experience_score NUMERIC(6,3) NOT NULL,
  readiness_score NUMERIC(6,3) NOT NULL,
  explanation_json JSONB NOT NULL,
  rank INT NOT NULL,
  ai_provider VARCHAR(60) NOT NULL DEFAULT 'local-fallback',
  computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (challenge_id, startup_id)
);
CREATE INDEX idx_match_results_challenge_id ON match_results(challenge_id);
CREATE INDEX idx_match_results_startup_id ON match_results(startup_id);
CREATE INDEX idx_match_results_rank ON match_results(challenge_id, rank);

-- =====================================================================================
-- 5. PROPOSALS & DOCUMENTS
-- =====================================================================================
CREATE TABLE proposals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  challenge_id UUID NOT NULL REFERENCES challenges(id) ON DELETE RESTRICT,
  startup_id UUID NOT NULL REFERENCES startups(id) ON DELETE RESTRICT,
  summary TEXT NOT NULL,
  proposed_approach TEXT,
  cost_estimate NUMERIC(14,2),
  timeline_estimate_days INT,
  status proposal_status NOT NULL DEFAULT 'SUBMITTED',
  submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (challenge_id, startup_id)
);
CREATE INDEX idx_proposals_challenge_id ON proposals(challenge_id);
CREATE INDEX idx_proposals_startup_id ON proposals(startup_id);
CREATE INDEX idx_proposals_status ON proposals(status);

CREATE TABLE documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_type document_owner_type NOT NULL,
  owner_id UUID NOT NULL,
  document_type document_type NOT NULL,
  file_path VARCHAR(500) NOT NULL,
  original_filename VARCHAR(255),
  verification_status verification_status NOT NULL DEFAULT 'PENDING',
  verification_notes TEXT,
  uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_documents_owner ON documents(owner_type, owner_id);
CREATE INDEX idx_documents_verification_status ON documents(verification_status);

-- =====================================================================================
-- 6. EVALUATION
-- =====================================================================================
CREATE TABLE evaluation_criteria (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  challenge_id UUID NOT NULL REFERENCES challenges(id) ON DELETE CASCADE,
  criterion_name VARCHAR(255) NOT NULL,
  max_score NUMERIC(6,2) NOT NULL DEFAULT 10.00,
  weight NUMERIC(5,2) NOT NULL DEFAULT 1.00
);
CREATE INDEX idx_evaluation_criteria_challenge_id ON evaluation_criteria(challenge_id);

CREATE TABLE evaluations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  proposal_id UUID NOT NULL REFERENCES proposals(id) ON DELETE CASCADE,
  expert_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  total_score NUMERIC(7,2),
  comments TEXT,
  ai_assist_summary TEXT,
  submitted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (proposal_id, expert_id)
);
CREATE INDEX idx_evaluations_proposal_id ON evaluations(proposal_id);
CREATE INDEX idx_evaluations_expert_id ON evaluations(expert_id);

CREATE TABLE evaluation_scores (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  evaluation_id UUID NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
  criterion_id UUID NOT NULL REFERENCES evaluation_criteria(id) ON DELETE RESTRICT,
  score NUMERIC(6,2) NOT NULL,
  remarks TEXT,
  UNIQUE (evaluation_id, criterion_id)
);
CREATE INDEX idx_evaluation_scores_evaluation_id ON evaluation_scores(evaluation_id);

-- =====================================================================================
-- 7. PILOTS, CONTRACTS, PAYMENTS
-- =====================================================================================
CREATE TABLE contracts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_value NUMERIC(14,2),
  ip_terms TEXT,
  data_terms TEXT,
  payment_terms TEXT,
  signed_date DATE,
  status contract_status NOT NULL DEFAULT 'DRAFT',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE pilots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  challenge_id UUID NOT NULL REFERENCES challenges(id) ON DELETE RESTRICT,
  startup_id UUID NOT NULL REFERENCES startups(id) ON DELETE RESTRICT,
  contract_id UUID REFERENCES contracts(id) ON DELETE SET NULL,
  start_date DATE NOT NULL,
  end_date DATE,
  status pilot_status NOT NULL DEFAULT 'ACTIVE',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_pilots_challenge_id ON pilots(challenge_id);
CREATE INDEX idx_pilots_startup_id ON pilots(startup_id);
CREATE INDEX idx_pilots_status ON pilots(status);

CREATE TABLE pilot_milestones (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pilot_id UUID NOT NULL REFERENCES pilots(id) ON DELETE CASCADE,
  title VARCHAR(255) NOT NULL,
  due_date DATE,
  status milestone_status NOT NULL DEFAULT 'PENDING',
  completion_date DATE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_pilot_milestones_pilot_id ON pilot_milestones(pilot_id);

CREATE TABLE payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id UUID NOT NULL REFERENCES contracts(id) ON DELETE RESTRICT,
  milestone_id UUID REFERENCES pilot_milestones(id) ON DELETE SET NULL,
  amount NUMERIC(14,2) NOT NULL,
  status payment_status NOT NULL DEFAULT 'PENDING',
  released_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_payments_contract_id ON payments(contract_id);
CREATE INDEX idx_payments_milestone_id ON payments(milestone_id);

-- =====================================================================================
-- 8. KPIs (pilot-level) & RECOMMENDATIONS
-- =====================================================================================
CREATE TABLE kpis (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pilot_id UUID NOT NULL REFERENCES pilots(id) ON DELETE CASCADE,
  kpi_name VARCHAR(255) NOT NULL,
  target_value NUMERIC(14,2),
  unit VARCHAR(60)
);
CREATE INDEX idx_kpis_pilot_id ON kpis(pilot_id);

CREATE TABLE kpi_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  kpi_id UUID NOT NULL REFERENCES kpis(id) ON DELETE CASCADE,
  recorded_value NUMERIC(14,2) NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  notes TEXT
);
CREATE INDEX idx_kpi_results_kpi_id ON kpi_results(kpi_id);

CREATE TABLE recommendations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pilot_id UUID NOT NULL UNIQUE REFERENCES pilots(id) ON DELETE CASCADE,
  recommendation recommendation_type NOT NULL,
  cost_score NUMERIC(6,3) NOT NULL,
  performance_score NUMERIC(6,3) NOT NULL,
  impact_score NUMERIC(6,3) NOT NULL,
  rationale_text TEXT NOT NULL,
  generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  reviewed_by UUID REFERENCES users(id) ON DELETE SET NULL,
  final_decision recommendation_type,
  decided_at TIMESTAMPTZ
);
CREATE INDEX idx_recommendations_pilot_id ON recommendations(pilot_id);

-- =====================================================================================
-- 9. KNOWLEDGE BASE
-- =====================================================================================
CREATE TABLE pilot_knowledge_base (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pilot_id UUID NOT NULL UNIQUE REFERENCES pilots(id) ON DELETE CASCADE,
  domain VARCHAR(120) NOT NULL,
  technology_tags TEXT[] NOT NULL DEFAULT '{}',
  department_id UUID NOT NULL REFERENCES government_departments(id) ON DELETE RESTRICT,
  outcome_summary TEXT,
  success BOOLEAN,
  searchable_text TEXT NOT NULL,
  embedding DOUBLE PRECISION[],
  embedding_model VARCHAR(100),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_pkb_domain ON pilot_knowledge_base(domain);
CREATE INDEX idx_pkb_department_id ON pilot_knowledge_base(department_id);
CREATE INDEX idx_pkb_success ON pilot_knowledge_base(success);
CREATE INDEX idx_pkb_technology_tags ON pilot_knowledge_base USING GIN (technology_tags);

-- =====================================================================================
-- 10. NOTIFICATIONS & AUDIT
-- =====================================================================================
CREATE TABLE notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  type notification_type NOT NULL,
  message TEXT NOT NULL,
  is_read BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_notifications_user_id ON notifications(user_id, is_read);

CREATE TABLE audit_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  actor_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  action VARCHAR(120) NOT NULL,
  entity_type VARCHAR(80) NOT NULL,
  entity_id UUID,
  metadata_json JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_logs_actor ON audit_logs(actor_user_id);
CREATE INDEX idx_audit_logs_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);

-- =====================================================================================
-- 11. AI CONFIG (configurable matching weights — Section 5 requirement)
-- =====================================================================================
CREATE TABLE ai_matching_config (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  config_key VARCHAR(80) NOT NULL UNIQUE,
  weight NUMERIC(5,3) NOT NULL,
  description TEXT
);

INSERT INTO roles (name, description) VALUES
  ('GOVERNMENT', 'Government department officials who publish challenges and manage pilots'),
  ('STARTUP', 'Startup companies who discover challenges and submit proposals'),
  ('EXPERT', 'Domain experts who evaluate proposals'),
  ('ADMIN', 'Platform administrators');

INSERT INTO ai_matching_config (config_key, weight, description) VALUES
  ('semantic_similarity', 0.35, 'Cosine similarity between challenge and startup embeddings'),
  ('technology_match', 0.20, 'Overlap between challenge desired technology and startup capability tags'),
  ('domain_match', 0.15, 'Overlap between challenge domain and startup domain tags'),
  ('experience_score', 0.15, 'Relevance/count of past projects in same or adjacent domain'),
  ('readiness_score', 0.15, 'Startup pilot-readiness score, normalized 0-1');
