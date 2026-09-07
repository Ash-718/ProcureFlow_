import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"
import { AuthProvider } from "@/hooks/useAuth"
import { RequireAuth } from "@/components/layout/require-auth"
import { AppShell } from "@/components/layout/app-shell"

import { LoginPage } from "@/pages/auth/login-page"
import { RegisterPage } from "@/pages/auth/register-page"

import { GovChallengesPage } from "@/pages/government/gov-challenges-page"
import { GovChallengeFormPage } from "@/pages/government/gov-challenge-form-page"
import { GovChallengeDetailPage } from "@/pages/government/gov-challenge-detail-page"
import { GovPilotsPage } from "@/pages/government/gov-pilots-page"
import { GovPilotDetailPage } from "@/pages/government/gov-pilot-detail-page"

import { StartupProfilePage } from "@/pages/startup/startup-profile-page"
import { StartupBrowseChallengesPage } from "@/pages/startup/startup-browse-challenges-page"
import { StartupChallengeDetailPage } from "@/pages/startup/startup-challenge-detail-page"
import { StartupProposalsPage } from "@/pages/startup/startup-proposals-page"

import { ExpertQueuePage } from "@/pages/expert/expert-queue-page"
import { ExpertEvaluatePage } from "@/pages/expert/expert-evaluate-page"

import { AdminUsersPage } from "@/pages/admin/admin-users-page"
import { AdminAuditLogsPage } from "@/pages/admin/admin-audit-logs-page"

import { KnowledgeBasePage } from "@/pages/shared/knowledge-base-page"

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          <Route element={<RequireAuth><AppShell /></RequireAuth>}>
            <Route
              path="/gov"
              element={<RequireAuth allow={["GOVERNMENT"]}><GovChallengesPage /></RequireAuth>}
            />
            <Route
              path="/gov/challenges/new"
              element={<RequireAuth allow={["GOVERNMENT"]}><GovChallengeFormPage /></RequireAuth>}
            />
            <Route
              path="/gov/challenges/:id"
              element={<RequireAuth allow={["GOVERNMENT"]}><GovChallengeDetailPage /></RequireAuth>}
            />
            <Route
              path="/gov/pilots"
              element={<RequireAuth allow={["GOVERNMENT"]}><GovPilotsPage /></RequireAuth>}
            />
            <Route
              path="/gov/pilots/:id"
              element={<RequireAuth allow={["GOVERNMENT"]}><GovPilotDetailPage /></RequireAuth>}
            />

            <Route
              path="/startup"
              element={<RequireAuth allow={["STARTUP"]}><StartupProfilePage /></RequireAuth>}
            />
            <Route
              path="/startup/challenges"
              element={<RequireAuth allow={["STARTUP"]}><StartupBrowseChallengesPage /></RequireAuth>}
            />
            <Route
              path="/startup/challenges/:id"
              element={<RequireAuth allow={["STARTUP"]}><StartupChallengeDetailPage /></RequireAuth>}
            />
            <Route
              path="/startup/proposals"
              element={<RequireAuth allow={["STARTUP"]}><StartupProposalsPage /></RequireAuth>}
            />

            <Route
              path="/expert"
              element={<RequireAuth allow={["EXPERT"]}><ExpertQueuePage /></RequireAuth>}
            />
            <Route
              path="/expert/proposals/:id"
              element={<RequireAuth allow={["EXPERT"]}><ExpertEvaluatePage /></RequireAuth>}
            />

            <Route
              path="/admin"
              element={<RequireAuth allow={["ADMIN"]}><AdminUsersPage /></RequireAuth>}
            />
            <Route
              path="/admin/audit-logs"
              element={<RequireAuth allow={["ADMIN"]}><AdminAuditLogsPage /></RequireAuth>}
            />

            <Route path="/knowledge-base" element={<KnowledgeBasePage />} />
          </Route>

          <Route path="/" element={<Navigate to="/login" replace />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
