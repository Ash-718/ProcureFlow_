import { Link } from 'react-router-dom'

import { useAuth } from '@/auth/AuthContext'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

const ROLE_BLURB: Record<string, string> = {
  GOVERNMENT: 'Post problems in plain language, review what the analyzer structures, and decide.',
  STARTUP: 'Browse challenges, apply, and report KPI evidence from your pilots.',
  EXPERT: 'Evaluate proposals independently and validate KPI evidence.',
  ADMIN: 'Maintain procurement rules and watch the fairness and audit trail.',
}

export function HomePage() {
  const { user } = useAuth()
  if (!user) return null

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold">ProcureFlow</h1>
        <p className="text-sm text-muted-foreground">
          Prototype for SIH26136 — Government of Maharashtra. All organisations and pilots shown
          are sample data.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            {user.full_name}
            <Badge variant="secondary">{user.role}</Badge>
          </CardTitle>
          <CardDescription>{ROLE_BLURB[user.role]}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-1 text-sm">
          <p>
            <span className="text-muted-foreground">Signed in as </span>
            {user.email}
          </p>
          {user.company && (
            <p>
              <span className="text-muted-foreground">Company </span>
              {user.company.name} ({user.company.district})
            </p>
          )}
          {user.department && (
            <p>
              <span className="text-muted-foreground">Department </span>
              {user.department.name}
            </p>
          )}
        </CardContent>
      </Card>

      {user.role === 'ADMIN' && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Procurement rules</CardTitle>
            <CardDescription>
              Every threshold, limit and percentage the engines use lives in the rules table.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link
              className="inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:opacity-90"
              to="/admin/rules"
            >
              View rules
            </Link>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Build status</CardTitle>
          <CardDescription>
            Phase 1 of six: database schema, authentication, role-based access and seed data. The
            role dashboards themselves are built in Phase 6.
          </CardDescription>
        </CardHeader>
      </Card>
    </div>
  )
}
