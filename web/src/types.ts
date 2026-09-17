export type Role = 'GOVERNMENT' | 'STARTUP' | 'EXPERT' | 'ADMIN'

export interface Challenge {
  id: number
  title: string
  description_raw: string
  department_id: number
  value: string | null
  criticality: string | null
  innovation_potential: string | null
  tier: string | null
  tier_explanation: string | null
  status: string
  district: string | null
  requires_onsite: boolean
  category: string | null
  structured_spec: Record<string, unknown> | null
  missing_fields: string[] | null
  kpis_locked: boolean
  published_at: string | null
  bid_closes_at: string | null
  kpis?: Kpi[]
}

export interface Kpi {
  id: number
  challenge_id: number
  startup_id: number | null
  name: string
  target_value: string | null
  unit: string | null
  measurement_method: string | null
  direction: 'HIGHER_IS_BETTER' | 'LOWER_IS_BETTER'
  claimed_value: string | null
  evidence: string | null
  validated_value: string | null
  validated_by: number | null
  validation_note: string | null
  status: string
}

export interface SuggestedKpi {
  name: string
  target_value: string | null
  unit: string
  measurement_method: string
  direction: 'HIGHER_IS_BETTER' | 'LOWER_IS_BETTER'
}

export interface Analysis {
  problem_statement: string
  required_capabilities: string[]
  expected_outcomes: string[]
  suggested_kpis: SuggestedKpi[]
  missing_fields: string[]
  budget: string | null
  timeline: string | null
  location: string | null
  source: string
  attempts: number
  notes: string[]
}

export interface SubScore {
  criterion: string
  score: number
  weight: number
  reason: string
}

export interface Match {
  company_id: number
  company_name: string
  total_score: number
  sub_scores: SubScore[]
  proximity: { applied: boolean; reason: string }
  track_record: Record<string, unknown>
  explanation: string
  disclaimer: string
}

export interface Proposal {
  id: number
  challenge_id: number
  startup_id: number
  summary: string | null
  status: string
  total_score: string | null
  sub_scores: {
    criteria?: SubScore[]
    proximity?: { applied: boolean; reason: string }
    track_record?: Record<string, unknown>
    explanation?: string
    disclaimer?: string
  } | null
  decline_reason_code: string | null
  decline_detail: string | null
  claimed_by_user_id: number | null
  expert_scores: { scores?: { criterion: string; score: number; reason: string }[] } | null
  expert_note: string | null
}

export interface Pilot {
  id: number
  challenge_id: number
  startup_id: number
  milestones: { name?: string; purpose?: string; kpi_checkpoint?: string }[] | null
  status: string
  recommended_outcome: string | null
  recommendation_reasoning: Record<string, unknown> | null
  outcome: string | null
  outcome_note: string | null
  cost: string | null
  lessons_learned: string | null
  started_on: string | null
  planned_end_on: string | null
  completed_on: string | null
}

export interface Recommendation {
  recommended_outcome: string
  kpis_total: number
  kpis_met: number
  kpis_missed: number
  on_schedule: boolean | null
  reasoning: string[]
  kpi_detail: {
    name: string
    target_value: string
    validated_value: string
    unit: string | null
    direction: string
    met: boolean
    reason: string
  }[]
  status: string
}

export interface PriorPilot {
  challenge_id: number
  title: string
  department: string
  startup: string
  outcome: string | null
  cost: string | null
  lessons_learned: string | null
  similarity: number
}

export interface BarrierFlag {
  code: string
  label: string
  detail: string
  excludes_startups: boolean | null
  classification: string
  reason: string
  rule_cited: string | null
  officer_action: string
}

export interface Fairness {
  founder_groups: {
    founders: string[]
    companies: string[]
    company_count: number
    awards: number
    total_value: string
    note: string | null
  }[]
  execution_firms: { firm: string; partnerships: number }[]
  startup_participation: {
    startup_awards: number
    total_awards: number
    share_pct: number
    target_pct: number | null
    meets_target?: boolean
    target_is_prototype_setting: boolean | null
    target_label: string
  }
  tier_distribution: { tier: string; challenges: number }[]
  totals: Record<string, unknown>
}

export interface AuditEntry {
  id: number
  created_at: string
  actor_label: string
  action: string
  entity_type: string | null
  entity_id: number | null
  reason: string | null
  details: Record<string, unknown> | null
}

export interface PartnershipView {
  partnership: {
    id: number
    challenge_id: number
    status: string
    milestone_status: { milestone: string; status: string; payment_to: string }[] | null
  }
  solution_owner: { role: string; company: string; district: string | null; scope: string }
  execution_partner: { role: string; company: string; district: string | null; scope: string }
  ip_note: string
  payment_note: string
}
