import { useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { describeError, Empty, ErrorNote, Section } from '@/components/common'
import { api } from '@/lib/api'
import type { PartnershipView } from '@/types'

export function PartnershipsPage() {
  const [partnershipId, setPartnershipId] = useState('')
  const [view, setView] = useState<PartnershipView | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function load() {
    setError(null)
    setView(null)
    try {
      setView(await api<PartnershipView>(`/partnerships/${partnershipId}`))
    } catch (err) {
      setError(describeError(err))
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Partnership</h1>
        <p className="text-sm text-muted-foreground">
          On a LARGE challenge the startup owns the solution and its IP, and a prime contractor
          executes within an assigned scope.
        </p>
      </div>

      <Section title="Open a partnership" description="Assigned after the startup's KPIs validate.">
        <div className="flex gap-2">
          <Input
            placeholder="Partnership id"
            value={partnershipId}
            onChange={(e) => setPartnershipId(e.target.value)}
          />
          <Button variant="outline" onClick={load} disabled={!partnershipId}>
            Open
          </Button>
        </div>
        <ErrorNote error={error} />
        {!view && !error && <Empty>Enter a partnership id to view it.</Empty>}
      </Section>

      {view && (
        <>
          <div className="grid gap-4 md:grid-cols-2">
            <Card className="border-primary">
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                  {view.solution_owner.role}
                  <Badge variant="default">owns the IP</Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <p className="font-medium">{view.solution_owner.company}</p>
                <p className="text-muted-foreground">{view.solution_owner.district}</p>
                <p>{view.solution_owner.scope}</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                  {view.execution_partner.role}
                  <Badge variant="secondary">executes assigned scope</Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <p className="font-medium">{view.execution_partner.company}</p>
                <p className="text-muted-foreground">{view.execution_partner.district}</p>
                <p>{view.execution_partner.scope}</p>
              </CardContent>
            </Card>
          </div>

          <Section title="Intellectual property" description="Who owns what.">
            <p className="text-sm">{view.ip_note}</p>
          </Section>

          <Section title="Milestones and payment" description={view.payment_note}>
            {(view.partnership.milestone_status ?? []).length === 0 ? (
              <Empty>No milestones recorded.</Empty>
            ) : (
              <div className="space-y-2">
                {(view.partnership.milestone_status ?? []).map((milestone) => (
                  <div
                    key={milestone.milestone}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border p-3 text-sm"
                  >
                    <span>{milestone.milestone}</span>
                    <span className="flex gap-2">
                      <Badge variant="outline">{milestone.status}</Badge>
                      <Badge variant="secondary">payment to {milestone.payment_to}</Badge>
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Section>
        </>
      )}
    </div>
  )
}
