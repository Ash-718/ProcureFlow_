import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { ArrowRight, BookOpenCheck, Cpu, Inbox, ScrollText } from "lucide-react"
import { ProposalApi } from "@/api/endpoints"
import { apiErrorMessage } from "@/api/client"
import type { Proposal } from "@/types"
import { Button } from "@/components/ui/button"
import { PageHeader, SectionHeader } from "@/components/ui/page-header"
import { StatCard, StatCardSkeleton, StatGrid } from "@/components/ui/stat-card"
import { EmptyState, ErrorState } from "@/components/ui/state-views"
import { formatDate } from "@/lib/utils"

/**
 * Expert home.
 *
 * The expert's job is narrow — evaluate what is queued — so this stays
 * deliberately small: the workload, the queue itself, and a statement of how
 * AI assistance is positioned relative to their judgement.
 *
 * Data: GET /proposals/queue. That is the only collection this role can read,
 * so the dashboard does not pretend to more.
 */
export function ExpertDashboardPage() {
  const [queue, setQueue] = useState<Proposal[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    setError(null)
    setQueue(null)
    ProposalApi.queue()
      .then(setQueue)
      .catch((err) => setError(apiErrorMessage(err)))
  }, [])

  useEffect(load, [load])

  const header = (
    <PageHeader
      title="Evaluation workspace"
      description="Proposals referred to you for independent assessment against each challenge's rubric."
      actions={
        <Button asChild variant="outline">
          <Link to="/expert/queue">
            <Inbox className="h-4 w-4" /> Open queue
          </Link>
        </Button>
      }
    />
  )

  if (error) {
    return (
      <div className="space-y-6">
        {header}
        <ErrorState message={error} onRetry={load} />
      </div>
    )
  }

  if (!queue) {
    return (
      <div className="space-y-6">
        {header}
        <StatGrid className="lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <StatCardSkeleton key={index} />
          ))}
        </StatGrid>
      </div>
    )
  }

  const challenges = new Set(queue.map((proposal) => proposal.challengeId))

  return (
    <div className="space-y-7">
      {header}

      <StatGrid className="lg:grid-cols-3">
        <StatCard
          label="Awaiting evaluation"
          value={queue.length}
          hint={queue.length > 0 ? "Referred to you for scoring" : "Your queue is clear"}
          icon={Inbox}
          tone={queue.length > 0 ? "warning" : "success"}
          to="/expert/queue"
        />
        <StatCard
          label="Challenges covered"
          value={challenges.size}
          hint="Distinct challenges in your queue"
          icon={ScrollText}
        />
        <StatCard
          label="Reference"
          value="Knowledge base"
          hint="Outcomes of comparable past pilots"
          icon={BookOpenCheck}
          to="/knowledge-base"
        />
      </StatGrid>

      {/* States the AI's role before the expert opens a proposal, rather than
          leaving them to infer it from a panel inside the evaluation form. */}
      <section className="rounded-lg border border-accent-100 bg-accent-50/60 p-5">
        <div className="flex gap-3">
          <Cpu className="mt-0.5 h-5 w-5 shrink-0 text-accent-600" aria-hidden />
          <div className="space-y-1">
            <h2 className="text-sm font-semibold text-accent-700">
              AI analysis assists your judgement — it does not replace it
            </h2>
            <p className="text-sm leading-relaxed text-slate-700">
              Each proposal carries a machine-generated analysis derived from the same
              scoring model used for challenge-wide matching. It is a starting point for
              your review. The score recorded against the rubric, and the recommendation
              that follows from it, are yours.
            </p>
          </div>
        </div>
      </section>

      <section className="space-y-3">
        <SectionHeader
          title="Your evaluation queue"
          icon={Inbox}
          actions={
            <Link
              to="/expert/queue"
              className="text-xs font-medium text-brand-700 hover:underline"
            >
              View all
            </Link>
          }
        />
        {queue.length === 0 ? (
          <EmptyState
            title="Nothing awaiting evaluation"
            description="Proposals appear here once a department refers them for expert assessment."
          />
        ) : (
          <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
            {queue.map((proposal) => (
              <li key={proposal.id}>
                <Link
                  to={`/expert/proposals/${proposal.id}`}
                  className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-slate-50"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-slate-900">
                      {proposal.companyName}
                    </p>
                    <p className="mt-0.5 truncate text-xs text-slate-500">
                      {proposal.challengeTitle} · submitted{" "}
                      {formatDate(proposal.submittedAt)}
                    </p>
                  </div>
                  <span className="hidden shrink-0 text-xs font-medium text-brand-700 sm:inline">
                    Evaluate
                  </span>
                  <ArrowRight className="h-4 w-4 shrink-0 text-slate-400" aria-hidden />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
