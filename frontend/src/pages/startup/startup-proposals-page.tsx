import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { ProposalApi } from "@/api/endpoints"
import { apiErrorMessage } from "@/api/client"
import type { Proposal } from "@/types"
import { StatusBadge } from "@/components/ui/status-badge"
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/state-views"
import { formatCurrencyInr, formatDate } from "@/lib/utils"

export function StartupProposalsPage() {
  const [proposals, setProposals] = useState<Proposal[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  function load() {
    setError(null)
    setProposals(null)
    ProposalApi.listMine().then(setProposals).catch((e) => setError(apiErrorMessage(e)))
  }
  useEffect(load, [])

  if (error) return <ErrorState message={error} onRetry={load} />
  if (!proposals) return <LoadingState label="Loading your proposals…" />

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-900">My Proposals</h1>
        <p className="text-sm text-slate-500">Track the status of every challenge you've responded to.</p>
      </div>

      {proposals.length === 0 ? (
        <EmptyState title="No proposals yet" description="Browse published challenges and submit your first proposal." />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-400">
                <th className="p-4">Challenge</th>
                <th className="p-4">Cost estimate</th>
                <th className="p-4">Submitted</th>
                <th className="p-4">Status</th>
              </tr>
            </thead>
            <tbody>
              {proposals.map((p) => (
                <tr key={p.id} className="border-b border-slate-100 last:border-0">
                  <td className="p-4">
                    <Link to={`/startup/challenges/${p.challengeId}`} className="font-medium text-brand-600 hover:underline">
                      {p.challengeTitle}
                    </Link>
                  </td>
                  <td className="p-4 text-slate-600">{formatCurrencyInr(p.costEstimate)}</td>
                  <td className="p-4 text-slate-500">{formatDate(p.submittedAt)}</td>
                  <td className="p-4"><StatusBadge status={p.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
