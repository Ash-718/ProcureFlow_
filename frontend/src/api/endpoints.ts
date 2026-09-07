import { apiClient } from "./client"
import type {
  AdminUser, AuditLogItem, AuthResponse, Challenge, ChallengeDraft, CurrentUser,
  DocumentItem, DocumentOwnerType, DocumentType, Evaluation, EvaluationCriterionItem,
  KnowledgeBaseEntry, MatchResponse, MatchResultRow, NotificationItem, Page, Pilot,
  Proposal, ProposalStatus, Recommendation, Role, SimilarPilotMatch, Startup,
  UpdateStartupProfileRequest,
} from "@/types"

export const AuthApi = {
  login: (email: string, password: string) =>
    apiClient.post<AuthResponse>("/auth/login", { email, password }).then((r) => r.data),
  register: (payload: {
    email: string; password: string; fullName: string; role: Role
    companyName?: string; departmentName?: string; ministry?: string; region?: string
  }) => apiClient.post<AuthResponse>("/auth/register", payload).then((r) => r.data),
  me: () => apiClient.get<CurrentUser>("/auth/me").then((r) => r.data),
}

export const ChallengeApi = {
  list: () => apiClient.get<Challenge[]>("/challenges").then((r) => r.data),
  get: (id: string) => apiClient.get<Challenge>(`/challenges/${id}`).then((r) => r.data),
  create: (payload: ChallengeDraft) => apiClient.post<Challenge>("/challenges", payload).then((r) => r.data),
  update: (id: string, payload: ChallengeDraft) =>
    apiClient.put<Challenge>(`/challenges/${id}`, payload).then((r) => r.data),
  publish: (id: string) => apiClient.post<Challenge>(`/challenges/${id}/publish`).then((r) => r.data),
}

export const StartupApi = {
  me: () => apiClient.get<Startup>("/startups/me").then((r) => r.data),
  updateMe: (payload: UpdateStartupProfileRequest) => apiClient.put<Startup>("/startups/me", payload).then((r) => r.data),
  addCapability: (payload: { technologyTag: string; domainTag: string; proficiencyLevel: number; description?: string }) =>
    apiClient.post<Startup>("/startups/me/capabilities", payload).then((r) => r.data),
  deleteCapability: (id: string) => apiClient.delete(`/startups/me/capabilities/${id}`),
  addProject: (payload: {
    title: string; domain: string; technologyStack?: string
    clientType: "GOVERNMENT" | "PRIVATE"; outcomeSummary?: string; year?: number
  }) => apiClient.post<Startup>("/startups/me/projects", payload).then((r) => r.data),
  list: () => apiClient.get<Startup[]>("/startups").then((r) => r.data),
  get: (id: string) => apiClient.get<Startup>(`/startups/${id}`).then((r) => r.data),
}

export const MatchingApi = {
  run: (challengeId: string) =>
    apiClient.post<MatchResponse>(`/matching/challenges/${challengeId}/run`).then((r) => r.data),
  results: (challengeId: string) =>
    apiClient.get<MatchResultRow[]>(`/matching/challenges/${challengeId}`).then((r) => r.data),
}

export const ProposalApi = {
  submit: (challengeId: string, payload: {
    summary: string; proposedApproach?: string; costEstimate?: number; timelineEstimateDays?: number
  }) => apiClient.post<Proposal>(`/proposals/challenges/${challengeId}`, payload).then((r) => r.data),
  listForChallenge: (challengeId: string) =>
    apiClient.get<Proposal[]>(`/proposals/challenges/${challengeId}`).then((r) => r.data),
  get: (id: string) => apiClient.get<Proposal>(`/proposals/${id}`).then((r) => r.data),
  listMine: () => apiClient.get<Proposal[]>("/proposals/mine").then((r) => r.data),
  queue: () => apiClient.get<Proposal[]>("/proposals/queue").then((r) => r.data),
  updateStatus: (id: string, status: ProposalStatus) =>
    apiClient.patch<Proposal>(`/proposals/${id}/status`, { status }).then((r) => r.data),
}

export const DocumentApi = {
  upload: (ownerType: DocumentOwnerType, ownerId: string, documentType: DocumentType, file: File) => {
    const form = new FormData()
    form.append("file", file)
    return apiClient
      .post<DocumentItem>(`/documents/${ownerType}/${ownerId}?documentType=${documentType}`, form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data)
  },
  list: (ownerType: DocumentOwnerType, ownerId: string) =>
    apiClient.get<DocumentItem[]>(`/documents/${ownerType}/${ownerId}`).then((r) => r.data),
}

export const EvaluationApi = {
  criteria: (proposalId: string) =>
    apiClient.get<EvaluationCriterionItem[]>(`/evaluations/proposals/${proposalId}/criteria`).then((r) => r.data),
  aiAnalysis: (proposalId: string) =>
    apiClient.get<{ summary: string }>(`/evaluations/proposals/${proposalId}/ai-analysis`).then((r) => r.data),
  submit: (proposalId: string, payload: {
    comments?: string; scores: { criterionId: string; score: number; remarks?: string }[]
  }) => apiClient.post<Evaluation>(`/evaluations/proposals/${proposalId}`, payload).then((r) => r.data),
}

export const PilotApi = {
  create: (payload: {
    challengeId: string; startupId: string; startDate: string; endDate?: string
    milestones: { title: string; dueDate?: string }[]
    kpis: { kpiName: string; targetValue?: number; unit?: string }[]
    contract?: { contractValue?: number; ipTerms?: string; dataTerms?: string; paymentTerms?: string }
  }) => apiClient.post<Pilot>("/pilots", payload).then((r) => r.data),
  get: (id: string) => apiClient.get<Pilot>(`/pilots/${id}`).then((r) => r.data),
  list: () => apiClient.get<Pilot[]>("/pilots").then((r) => r.data),
  updateMilestone: (pilotId: string, milestoneId: string, status: string, completionDate?: string) =>
    apiClient.patch<Pilot>(`/pilots/${pilotId}/milestones/${milestoneId}`, { status, completionDate }).then((r) => r.data),
  addKpiResult: (pilotId: string, kpiId: string, recordedValue: number, notes?: string) =>
    apiClient.post<Pilot>(`/pilots/${pilotId}/kpis/${kpiId}/results`, { recordedValue, notes }).then((r) => r.data),
  complete: (pilotId: string, finalStatus: "COMPLETED" | "TERMINATED") =>
    apiClient.post<Pilot>(`/pilots/${pilotId}/complete`, { finalStatus }).then((r) => r.data),
  recommendation: (pilotId: string) =>
    apiClient.get<Recommendation>(`/pilots/${pilotId}/recommendation`).then((r) => r.data),
  decide: (pilotId: string, finalDecision: string) =>
    apiClient.post<Recommendation>(`/pilots/${pilotId}/recommendation/decision`, { finalDecision }).then((r) => r.data),
}

export const KnowledgeBaseApi = {
  search: (params: { domain?: string; technology?: string; success?: boolean; q?: string }) =>
    apiClient.get<KnowledgeBaseEntry[]>("/knowledge-base", { params }).then((r) => r.data),
  similarForDraft: (payload: {
    title: string; problemStatement: string; desiredTechnology?: string; domain: string; outcomesExpected?: string
  }) => apiClient.post<{ aiProvider: string; results: SimilarPilotMatch[] }>("/knowledge-base/similar-for-draft", payload)
    .then((r) => r.data),
}

export const NotificationApi = {
  list: () => apiClient.get<NotificationItem[]>("/notifications").then((r) => r.data),
  unreadCount: () => apiClient.get<{ unread: number }>("/notifications/unread-count").then((r) => r.data),
  markRead: (id: string) => apiClient.patch(`/notifications/${id}/read`),
}

export const AdminApi = {
  listUsers: () => apiClient.get<AdminUser[]>("/admin/users").then((r) => r.data),
  setActive: (id: string, active: boolean) =>
    apiClient.patch<AdminUser>(`/admin/users/${id}/active`, { active }).then((r) => r.data),
  auditLogs: (page = 0, size = 50) =>
    apiClient.get<Page<AuditLogItem>>("/admin/audit-logs", { params: { page, size } }).then((r) => r.data),
}
