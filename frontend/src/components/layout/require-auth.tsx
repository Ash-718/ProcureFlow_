import { Navigate, useLocation } from "react-router-dom"
import { useAuth } from "@/hooks/useAuth"
import { LoadingState } from "@/components/ui/state-views"
import { ROLE_HOME } from "./nav-config"
import type { Role } from "@/types"

export function RequireAuth({ allow, children }: { allow?: Role[]; children: React.ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) return <LoadingState label="Checking your session…" />
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />
  if (allow && !allow.includes(user.role)) return <Navigate to={ROLE_HOME[user.role]} replace />

  return <>{children}</>
}
