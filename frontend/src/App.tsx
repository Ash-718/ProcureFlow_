import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"
import { AuthProvider } from "@/hooks/useAuth"
import { RequireAuth } from "@/components/layout/require-auth"
import { AppShell } from "@/components/layout/app-shell"

import { LoginPage } from "@/pages/auth/login-page"
import { RegisterPage } from "@/pages/auth/register-page"

import { GovDashboardPage } from "@/pages/government/gov-dashboard-page"
import { GovChallengesPage } from "@/pages/government/gov-challenges-page"
import { GovChallengeFormPage } from "@/pages/government/gov-challenge-form-page"
import { GovChallengeDetailPage } from "@/pages/government/gov-challenge-detail-page"
import { GovPilotsPage } from "@/pages/government/gov-pilots-page"
import { GovPilotDetailPage } from "@/pages/government/gov-pilot-detail-page"

import { StartupDashboardPage } from "@/pages/startup/startup-dashboard-page"
import { StartupProfilePage } from "@/pages/startup/startup-profile-page"
import { StartupBrowseChallengesPage } from "@/pages/startup/startup-browse-challenges-page"
import { StartupChallengeDetailPage } from "@/pages/startup/startup-challenge-detail-page"
import { StartupProposalsPage } from "@/pages/startup/startup-proposals-page"

import { ExpertDashboardPage } from "@/pages/expert/expert-dashboard-page"
import { ExpertQueuePage } from "@/pages/expert/expert-queue-page"
import { ExpertEvaluatePage } from "@/pages/expert/expert-evaluate-page"

import { AdminDashboardPage } from "@/pages/admin/admin-dashboard-page"
import { AdminUsersPage } from "@/pages/admin/admin-users-page"
import { AdminAuditLogsPage } from "@/pages/admin/admin-audit-logs-page"

import { KnowledgeBasePage } from "@/pages/shared/knowledge-base-page"

/**
 * Routes.
 *
 * Each role's home (`/gov`, `/startup`, `/expert`, `/admin`) is now a
 * dashboard; the list pages that previously occupied those paths moved to
 * explicit routes (`/gov/challenges`, `/startup/profile`, `/expert/queue`,
 * `/admin/users`).
 *
 * `/startup` and `/expert` previously *were* the profile and queue pages, so
 * a redirect preserves any bookmark pointing at the old location rather than
 * silently changing what those URLs show. Role guards are unchanged.
 */
export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          <Route element={<RequireAuth><AppShell /></RequireAuth>}>
            {/* ---------------------------------------------- Government */}
            <Route
              path="/gov"
              element={<RequireAuth allow={["GOVERNMENT"]}><GovDashboardPage /></RequireAuth>}
            />
            <Route
              path="/gov/challenges"
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

            {/* ------------------------------------------------- Startup */}
            <Route
              path="/startup"
              element={<RequireAuth allow={["STARTUP"]}><StartupDashboardPage /></RequireAuth>}
            />
            <Route
              path="/startup/profile"
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

            {/* -------------------------------------------------- Expert */}
            <Route
              path="/expert"
              element={<RequireAuth allow={["EXPERT"]}><ExpertDashboardPage /></RequireAuth>}
            />
            <Route
              path="/expert/queue"
              element={<RequireAuth allow={["EXPERT"]}><ExpertQueuePage /></RequireAuth>}
            />
            <Route
              path="/expert/proposals/:id"
              element={<RequireAuth allow={["EXPERT"]}><ExpertEvaluatePage /></RequireAuth>}
            />

            {/* --------------------------------------------------- Admin */}
            <Route
              path="/admin"
              element={<RequireAuth allow={["ADMIN"]}><AdminDashboardPage /></RequireAuth>}
            />
            <Route
              path="/admin/users"
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
