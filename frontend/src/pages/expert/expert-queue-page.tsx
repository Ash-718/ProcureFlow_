import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { ArrowRight } from "lucide-react"
import { ProposalApi } from "@/api/endpoints"
import { apiErrorMessage } from "@/api/client"
import type { Proposal } from "@/types"
import { Card, CardContent } from "@/components/ui/card"
import { StatusBadge } from "@/components/ui/status-badge"
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/state-views"
import { formatCurrencyInr, formatDate } from "@/lib/utils"

export function ExpertQueuePage() {
  const [proposals, setProposals] = useState<Proposal[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  function load() {
    setError(null)
    setProposals(null)
    ProposalApi.queue().then(setProposals).catch((e) => setError(apiErrorMessage(e)))
  }
  useEffect(load, [])

  if (error) return <ErrorState message={error} onRetry={load} />
  if (!proposals) return <LoadingState label="Loading evaluation queue…" />

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Evaluation Queue</h1>
        <p className="text-sm text-slate-500">
          Proposals awaiting expert review, with AI-assisted analysis to support — not replace — your judgment.
        </p>
      </div>

      {proposals.length === 0 ? (
        <EmptyState title="Queue is empty" description="No proposals are currently awaiting evaluation." />
      ) : (
        <div className="space-y-3">
          {proposals.map((p) => (
            <Link key={p.id} to={`/expert/proposals/${p.id}`}>
              <Card className="transition-shadow hover:shadow-md">
                <CardContent className="flex items-center justify-between gap-4 p-4">
                  <div>
                    <p className="font-medium text-slate-800">{p.companyName} → {p.challengeTitle}</p>
                    <p className="text-xs text-slate-400">
                      Submitted {formatDate(p.submittedAt)} · Cost estimate {formatCurrencyInr(p.costEstimate)}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <StatusBadge status={p.status} />
                    <ArrowRight className="h-4 w-4 text-slate-400" />
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
