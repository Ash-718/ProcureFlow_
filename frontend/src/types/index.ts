export type Role = "GOVERNMENT" | "STARTUP" | "EXPERT" | "ADMIN"

export interface AuthResponse {
  token: string
  userId: string
  email: string
  fullName: string
  role: Role
}

export interface CurrentUser {
  id: string
  email: string
  fullName: string
  role: Role
}

export type ChallengeStatus = "DRAFT" | "PUBLISHED" | "MATCHING" | "SHORTLISTED" | "PILOT" | "CLOSED"
export type RequirementType = "ELIGIBILITY" | "TECHNICAL" | "COMPLIANCE"

export interface ChallengeRequirement {
  id: string
  requirementType: RequirementType
  description: string
  mandatory: boolean
}

export interface ChallengeKpi {
  id: string
  kpiName: string
  targetValue: number | null
  unit: string | null
  weight: number
}

export interface Challenge {
  id: string
  departmentId: string
  departmentName: string
  title: string
  problemStatement: string
  desiredTechnology: string | null
  domain: string
  outcomesExpected: string | null
  budgetRange: string | null
  timelineDays: number | null
  status: ChallengeStatus
  publishedAt: string | null
  requirements: ChallengeRequirement[]
  kpis: ChallengeKpi[]
}

export interface ChallengeDraft {
  title: string
  problemStatement: string
  desiredTechnology?: string
  domain: string
  outcomesExpected?: string
  budgetRange?: string
  timelineDays?: number
  requirements: { requirementType: RequirementType; description: string; mandatory: boolean }[]
  kpis: { kpiName: string; targetValue?: number; unit?: string; weight?: number }[]
}

export interface StartupCapability {
  id: string
  technologyTag: string
  domainTag: string
  proficiencyLevel: number
  description: string | null
}

export interface StartupProject {
  id: string
  title: string
  domain: string
  technologyStack: string | null
  clientType: "GOVERNMENT" | "PRIVATE"
  outcomeSummary: string | null
  year: number | null
}

export interface UpdateStartupProfileRequest {
  companyName: string
  dpiitNumber?: string
  foundedYear?: number
  teamSize?: number
  city?: string
  state?: string
  description?: string
  readinessScore?: number
}

export interface Startup {
  id: string
  companyName: string
  dpiitNumber: string | null
  foundedYear: number | null
  teamSize: number | null
  city: string | null
  state: string | null
  readinessScore: number
  description: string | null
  capabilities: StartupCapability[]
  projects: StartupProject[]
}

export interface ComponentScores {
  semanticSimilarity: number
  technologyMatch: number
  domainMatch: number
  experienceScore: number
  readinessScore: number
}

export interface MatchCandidate {
  startupId: string
  companyName: string
  rank: number
  overallScore: number
  componentScores: ComponentScores
  reasons: string[]
  gaps: string[]
}

export interface MatchResponse {
  challengeId: string
  aiProvider: string
  weights: Record<string, number>
  totalCandidatesConsidered: number
  results: MatchCandidate[]
}

export interface MatchResultRow {
  startupId: string
  companyName: string
  rank: number
  overallScore: number
  semanticSimilarityScore: number
  technologyMatchScore: number
  domainMatchScore: number
  experienceScore: number
  readinessScore: number
  reasons: string[]
  gaps: string[]
  aiProvider: string
}

export type ProposalStatus = "SUBMITTED" | "UNDER_REVIEW" | "SHORTLISTED" | "REJECTED"

export interface Proposal {
  id: string
  challengeId: string
  challengeTitle: string
  startupId: string
  companyName: string
  summary: string
  proposedApproach: string | null
  costEstimate: number | null
  timelineEstimateDays: number | null
  status: ProposalStatus
  submittedAt: string
}

export type DocumentOwnerType = "STARTUP" | "PROPOSAL"
export type DocumentType = "ELIGIBILITY" | "COMPLIANCE" | "FINANCIAL" | "OTHER"
export type VerificationStatus = "PENDING" | "VERIFIED" | "FLAGGED"

export interface DocumentItem {
  id: string
  ownerType: DocumentOwnerType
  ownerId: string
  documentType: DocumentType
  originalFilename: string | null
  verificationStatus: VerificationStatus
  verificationNotes: string | null
  uploadedAt: string
}

export interface EvaluationCriterionItem {
  id: string
  criterionName: string
  maxScore: number
  weight: number
}

export interface EvaluationScoreItem {
  criterionId: string
  criterionName: string
  score: number
  remarks: string | null
}

export interface Evaluation {
  id: string
  proposalId: string
  expertId: string
  expertName: string
  totalScore: number | null
  comments: string | null
  aiAssistSummary: string | null
  submittedAt: string | null
  scores: EvaluationScoreItem[]
}

export type MilestoneStatus = "PENDING" | "IN_PROGRESS" | "DONE" | "DELAYED"
export type PilotStatus = "ACTIVE" | "COMPLETED" | "TERMINATED"
export type RecommendationType = "SCALE" | "MODIFY" | "REJECT"

export interface PilotMilestoneItem {
  id: string
  title: string
  dueDate: string | null
  status: MilestoneStatus
  completionDate: string | null
}

export interface PilotKpiItem {
  id: string
  kpiName: string
  targetValue: number | null
  unit: string | null
  latestRecordedValue: number | null
  latestRecordedAt: string | null
}

export interface PilotContract {
  id: string
  contractValue: number | null
  ipTerms: string | null
  dataTerms: string | null
  paymentTerms: string | null
  status: string
}

export interface Pilot {
  id: string
  challengeId: string
  challengeTitle: string
  startupId: string
  companyName: string
  startDate: string
  endDate: string | null
  status: PilotStatus
  milestones: PilotMilestoneItem[]
  kpis: PilotKpiItem[]
  contract: PilotContract | null
}

export interface Recommendation {
  id: string
  pilotId: string
  recommendation: RecommendationType
  costScore: number
  performanceScore: number
  impactScore: number
  rationaleText: string
  generatedAt: string
  reviewedByName: string | null
  finalDecision: RecommendationType | null
  decidedAt: string | null
}

export interface KnowledgeBaseEntry {
  id: string
  pilotId: string
  challengeTitle: string
  domain: string
  technologyTags: string[]
  departmentName: string
  startupName: string
  outcomeSummary: string | null
  success: boolean | null
  createdAt: string
}

export interface SimilarPilotMatch {
  pilotId: string
  challengeTitle: string
  domain: string
  technologyTags: string[]
  outcomeSummary: string | null
  success: boolean | null
  similarity: number
}

export type NotificationType =
  | "MATCH_READY" | "PROPOSAL_SUBMITTED" | "PROPOSAL_STATUS_CHANGE" | "DOCUMENT_VERIFIED"
  | "DOCUMENT_FLAGGED" | "EVALUATION_ASSIGNED" | "EVALUATION_SUBMITTED" | "SHORTLISTED"
  | "PILOT_CREATED" | "MILESTONE_DUE" | "MILESTONE_UPDATED" | "RECOMMENDATION_READY" | "GENERAL"

export interface NotificationItem {
  id: string
  type: NotificationType
  message: string
  read: boolean
  createdAt: string
}

export interface AdminUser {
  id: string
  email: string
  fullName: string
  role: Role
  active: boolean
  createdAt: string
}

export interface AuditLogItem {
  id: string
  actorEmail: string | null
  action: string
  entityType: string
  entityId: string | null
  metadataJson: string | null
  createdAt: string
}

export interface Page<T> {
  content: T[]
  totalElements: number
  totalPages: number
  number: number
  size: number
}

export interface ApiErrorBody {
  timestamp: string
  status: number
  error: string
  message: string
  path: string
  fieldErrors?: Record<string, string>
}
