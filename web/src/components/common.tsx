import type { ReactNode } from 'react'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { SubScore } from '@/types'

export function Section({
  title,
  description,
  children,
  action,
}: {
  title: string
  description?: string
  children: ReactNode
  action?: ReactNode
}) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <CardTitle className="text-base">{title}</CardTitle>
            {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
          </div>
          {action}
        </div>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="text-sm text-muted-foreground">{children}</p>
}

export function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <p className="text-sm">
      <span className="text-muted-foreground">{label} </span>
      {value ?? <span className="text-muted-foreground">—</span>}
    </p>
  )
}

export function MissingFields({ fields }: { fields: string[] | null | undefined }) {
  if (!fields || fields.length === 0) {
    return <Badge variant="outline">Nothing outstanding</Badge>
  }
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1">
        {fields.map((field) => (
          <Badge key={field} variant="warning">
            {field}
          </Badge>
        ))}
      </div>
      <p className="text-xs text-muted-foreground">
        The analyzer reports these as missing rather than filling them in. Publishing stays
        blocked until the department supplies them.
      </p>
    </div>
  )
}

/** Sub-scores with the reason for each. Never a bare number. */
export function SubScoreTable({
  subScores,
  proximity,
}: {
  subScores: SubScore[]
  proximity?: { applied: boolean; reason: string }
}) {
  return (
    <div className="space-y-2">
      {subScores.map((sub) => (
        <div key={sub.criterion} className="rounded-md border border-border p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-sm font-medium">{sub.criterion.replace(/_/g, ' ')}</span>
            <span className="flex items-center gap-2 text-sm">
              <Badge variant="secondary">{sub.score.toFixed(0)} / 100</Badge>
              <span className="text-xs text-muted-foreground">
                weight {(sub.weight * 100).toFixed(0)}%
              </span>
            </span>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">{sub.reason}</p>
        </div>
      ))}
      {proximity && (
        <div className="rounded-md border border-dashed border-border p-3">
          <span className="text-sm font-medium">proximity</span>
          <p className="mt-1 text-xs text-muted-foreground">{proximity.reason}</p>
        </div>
      )}
      <p className="text-xs text-muted-foreground">
        Prototype-generated scores. Not official evaluation criteria.
      </p>
    </div>
  )
}

export function ErrorNote({ error }: { error: string | null }) {
  if (!error) return null
  return <p className="text-sm text-destructive">{error}</p>
}

export function describeError(error: unknown): string {
  if (error instanceof Error) {
    try {
      const parsed = JSON.parse(error.message)
      if (parsed?.message) return String(parsed.message)
    } catch {
      // Not JSON: the message is already readable.
    }
    return error.message
  }
  return 'Something went wrong'
}
