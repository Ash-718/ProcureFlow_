import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { ArrowRight } from "lucide-react"
import { PilotApi } from "@/api/endpoints"
import { apiErrorMessage } from "@/api/client"
import type { Pilot } from "@/types"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { StatusBadge } from "@/components/ui/status-badge"
import { CardSkeletonGrid, EmptyState, ErrorState } from "@/components/ui/state-views"
import { formatDate } from "@/lib/utils"

export function GovPilotsPage() {
  const [pilots, setPilots] = useState<Pilot[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  function load() {
    setError(null)
    setPilots(null)
    PilotApi.list().then(setPilots).catch((e) => setError(apiErrorMessage(e)))
  }
  useEffect(load, [])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Pilots</h1>
        <p className="text-sm text-slate-500">Controlled pilots running against shortlisted startups.</p>
      </div>

      {error && <ErrorState message={error} onRetry={load} />}
      {!error && pilots === null && <CardSkeletonGrid />}
      {!error && pilots?.length === 0 && (
        <EmptyState title="No pilots yet" description="Shortlist a proposal from a challenge and create a pilot to track it here." />
      )}
      {!error && pilots && pilots.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {pilots.map((p) => (
            <Link key={p.id} to={`/gov/pilots/${p.id}`}>
              <Card className="h-full transition-shadow hover:shadow-md">
                <CardHeader>
                  <div className="flex items-start justify-between gap-2">
                    <CardTitle className="line-clamp-2">{p.challengeTitle}</CardTitle>
                    <StatusBadge status={p.status} />
                  </div>
                </CardHeader>
                <CardContent className="space-y-2">
                  <p className="text-sm font-medium text-slate-700">{p.companyName}</p>
                  <p className="text-xs text-slate-500">
                    {formatDate(p.startDate)} {p.endDate && `→ ${formatDate(p.endDate)}`}
                  </p>
                  <div className="flex items-center gap-1 text-sm font-medium text-brand-600">
                    View details <ArrowRight className="h-3.5 w-3.5" />
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
