import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'

import { useAuth, type Role } from '@/auth/AuthContext'

/**
 * Client-side RBAC.
 *
 * This hides screens a role should not see.  It is a convenience, not a
 * security boundary: every endpoint behind these screens enforces the same
 * rule again on the server.
 */
export function RequireRole({ allow, children }: { allow: Role[]; children: ReactNode }) {
  const { user, loading } = useAuth()

  if (loading) {
    return <p className="p-8 text-sm text-muted-foreground">Loading…</p>
  }
  if (!user) {
    return <Navigate to="/login" replace />
  }
  if (!allow.includes(user.role)) {
    return (
      <div className="p-8">
        <h2 className="text-lg font-semibold">Not available for your role</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          You are signed in as {user.role}. This screen is for {allow.join(' or ')}.
        </p>
      </div>
    )
  }
  return <>{children}</>
}
