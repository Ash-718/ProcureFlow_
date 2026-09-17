import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AuthProvider, useAuth } from '@/auth/AuthContext'
import { Layout } from '@/components/Layout'
import { RequireRole } from '@/components/RequireRole'
import { AdminRulesPage } from '@/pages/AdminRulesPage'
import { ExpertEvaluation } from '@/pages/ExpertEvaluation'
import { FairnessDashboard } from '@/pages/FairnessDashboard'
import { GovernmentDashboard } from '@/pages/GovernmentDashboard'
import { LoginPage } from '@/pages/LoginPage'
import { PartnershipsPage } from '@/pages/PartnershipsPage'
import { StartupPortal } from '@/pages/StartupPortal'

/** Where each role lands after signing in. */
const HOME_FOR_ROLE = {
  GOVERNMENT: '/government',
  STARTUP: '/startup',
  EXPERT: '/evaluation',
  ADMIN: '/fairness',
} as const

function RoleHome() {
  const { user, loading } = useAuth()
  if (loading) return <p className="p-8 text-sm text-muted-foreground">Loading…</p>
  if (!user) return <Navigate to="/login" replace />
  return <Navigate to={HOME_FOR_ROLE[user.role]} replace />
}

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <p className="p-8 text-sm text-muted-foreground">Loading…</p>
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            element={
              <RequireAuth>
                <Layout />
              </RequireAuth>
            }
          >
            <Route path="/" element={<RoleHome />} />
            <Route
              path="/government"
              element={
                <RequireRole allow={['GOVERNMENT']}>
                  <GovernmentDashboard />
                </RequireRole>
              }
            />
            <Route
              path="/startup"
              element={
                <RequireRole allow={['STARTUP']}>
                  <StartupPortal />
                </RequireRole>
              }
            />
            <Route
              path="/evaluation"
              element={
                <RequireRole allow={['EXPERT']}>
                  <ExpertEvaluation />
                </RequireRole>
              }
            />
            <Route
              path="/partnerships"
              element={
                <RequireRole allow={['GOVERNMENT', 'ADMIN']}>
                  <PartnershipsPage />
                </RequireRole>
              }
            />
            <Route
              path="/fairness"
              element={
                <RequireRole allow={['ADMIN']}>
                  <FairnessDashboard />
                </RequireRole>
              }
            />
            <Route
              path="/admin/rules"
              element={
                <RequireRole allow={['ADMIN']}>
                  <AdminRulesPage />
                </RequireRole>
              }
            />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
