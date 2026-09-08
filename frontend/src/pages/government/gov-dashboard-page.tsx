import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router-dom"
import {
  ArrowRight,
  ClipboardList,
  FileText,
  Gavel,
  Plus,
  Rocket,
  Target,
} from "lucide-react"
import { ChallengeApi, PilotApi, ProposalApi } from "@/api/endpoints"
import { apiErrorMessage } from "@/api/client"
import type { Challenge, Pilot, Proposal, Recommendation } from "@/types"
import { Button } from "@/components/ui/button"
import { PageHeader, SectionHeader } from "@/components/ui/page-header"
import { StatCard, StatCardSkeleton, StatGrid } from "@/components/ui/stat-card"
import { StatusBadge } from "@/components/ui/status-badge"
import { EmptyState, ErrorState } from "@/components/ui/state-views"
import { WorkflowRail } from "@/components/workflow-rail"
import { kpiHealth } from "@/lib/kpi"
import { formatDate } from "@/lib/utils"

/**
 * Government home.
 *
 * Answers "what needs my attention?" first and browsing second — the previous
 * home was the challenge list, which showed inventory but no state.
 *
 * Every figure is derived from real API responses:
 *   GET /challenges                          -> counts by status
 *   GET /pilots                              -> counts, KPI health
 *   GET /proposals/challenges/{id}           -> proposals awaiting review
 *   GET /pilots/{id}/recommendation          -> decisions outstanding
 *
 * The per-challenge proposal fetch is an N+1, which is acceptable here: a
 * department owns a handful of challenges (two in the seeded data) and the
 * requests are issued in parallel. If a department ever owned hundreds, this
 * would need a summary endpoint rather than a client-side fan-out.
 */

interface DashboardData {
  challenges: Challenge[]
  pilots: Pilot[]
  proposals: Proposal[]
  recommendations: { pilot: Pilot; recommendation: Recommendation }[]
}

export function GovDashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    setError(null)
    setData(null)

    Promise.all([ChallengeApi.list(), PilotApi.list()])
      .then(async ([challenges, pilots]) => {
        // Fan out in parallel rather than sequentially.
        const proposalLists = await Promise.all(
          challenges.map((challenge) =>
            ProposalApi.listForChallenge(challenge.id).catch(() => [] as Proposal[]),
          ),
        )
        // A pilot only has a recommendation once it has been completed; a 404
        // is the normal answer for an active one, not an error.
        const recommendations = await Promise.all(
          pilots.map(async (pilot) => {
            try {
              return { pilot, recommendation: await PilotApi.recommendation(pilot.id) }
            } catch {
              return null
            }
          }),
        )

        setData({
          challenges,
          pilots,
          proposals: proposalLists.flat(),
          recommendations: recommendations.filter(
            (entry): entry is { pilot: Pilot; recommendation: Recommendation } =>
              entry !== null,
          ),
        })
      })
      .catch((err) => setError(apiErrorMessage(err)))
  }, [])

  useEffect(load, [load])

  const header = (
    <PageHeader
      title="Department dashboard"
      description="Challenges, proposals and pilots your department is responsible for."
      actions={
        <Button asChild>
          <Link to="/gov/challenges/new">
            <Plus className="h-4 w-4" /> New challenge
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

  if (!data) {
    return (
      <div className="space-y-6">
        {header}
        <StatGrid>
          {Array.from({ length: 4 }).map((_, index) => (
            <StatCardSkeleton key={index} />
          ))}
        </StatGrid>
      </div>
    )
  }

  const { challenges, pilots, proposals, recommendations } = data

  const activeChallenges = challenges.filter(
    (challenge) => !["DRAFT", "CLOSED"].includes(challenge.status),
  )
  const draftChallenges = challenges.filter((challenge) => challenge.status === "DRAFT")
  const awaitingReview = proposals.filter((proposal) => proposal.status === "SUBMITTED")
  const activePilots = pilots.filter((pilot) => pilot.status === "ACTIVE")
  const pendingDecisions = recommendations.filter(
    (entry) => entry.recommendation.finalDecision === null,
  )

  // KPI health across every pilot that has at least one assessable KPI.
  const allKpis = pilots.flatMap((pilot) => pilot.kpis)
  const health = kpiHealth(allKpis)

  return (
    <div className="space-y-7">
      {header}

      <StatGrid>
        <StatCard
          label="Active challenges"
          value={activeChallenges.length}
          hint={draftChallenges.length > 0 ? `${draftChallenges.length} in draft` : "None in draft"}
          icon={FileText}
          to="/gov/challenges"
        />
        <StatCard
          label="Proposals to review"
          value={awaitingReview.length}
          hint={`${proposals.length} received in total`}
          icon={ClipboardList}
          tone={awaitingReview.length > 0 ? "warning" : "neutral"}
        />
        <StatCard
          label="Active pilots"
          value={activePilots.length}
          hint={`${pilots.length} pilot${pilots.length === 1 ? "" : "s"} overall`}
          icon={Rocket}
          to="/gov/pilots"
        />
        <StatCard
          label="Decisions outstanding"
          value={pendingDecisions.length}
          hint={
            pendingDecisions.length > 0
              ? "A completed pilot is awaiting your decision"
              : "No pilot is waiting on you"
          }
          icon={Gavel}
          tone={pendingDecisions.length > 0 ? "warning" : "neutral"}
        />
      </StatGrid>

      {/* The lifecycle, so the platform's shape is visible on the landing
          screen rather than only implied by the navigation. */}
      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <SectionHeader
          title="Procurement lifecycle"
          description="Every challenge moves through these stages, from a departmental problem to reusable institutional knowledge."
        />
        <div className="mt-4">
          <WorkflowRail current="MATCHING" />
        </div>
      </section>

      {pendingDecisions.length > 0 && (
        <section className="space-y-3">
          <SectionHeader
            title="Awaiting your decision"
            description="These pilots have completed and the system has produced a recommendation. The decision is yours."
            icon={Gavel}
          />
          <ul className="space-y-2">
            {pendingDecisions.map(({ pilot, recommendation }) => (
              <li key={pilot.id}>
                <Link
                  to={`/gov/pilots/${pilot.id}`}
                  className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-warning-100 bg-warning-50/60 px-4 py-3 transition-colors hover:border-warning-500"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-slate-900">
                      {pilot.challengeTitle}
                    </p>
                    <p className="text-xs text-slate-600">{pilot.companyName}</p>
                  </div>
                  <div className="flex items-center gap-2 text-xs">
                    <span className="text-slate-500">System recommends</span>
                    <StatusBadge status={recommendation.recommendation} />
                  </div>
                  <ArrowRight className="h-4 w-4 shrink-0 text-slate-400" aria-hidden />
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="space-y-3">
          <SectionHeader
            title="Active challenges"
            icon={FileText}
            actions={
              <Link
                to="/gov/challenges"
                className="text-xs font-medium text-brand-700 hover:underline"
              >
                View all
              </Link>
            }
          />
          {activeChallenges.length === 0 ? (
            <EmptyState
              title="No active challenges"
              description="Publish a challenge to start discovering startups that can solve it."
              action={
                <Button asChild size="sm">
                  <Link to="/gov/challenges/new">
                    <Plus className="h-4 w-4" /> New challenge
                  </Link>
                </Button>
              }
            />
          ) : (
            <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
              {activeChallenges.slice(0, 5).map((challenge) => (
                <li key={challenge.id}>
                  <Link
                    to={`/gov/challenges/${challenge.id}`}
                    className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-slate-50"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-slate-900">
                        {challenge.title}
                      </p>
                      <p className="mt-0.5 text-xs text-slate-500">
                        {challenge.domain} · {challenge.kpis.length} KPI
                        {challenge.kpis.length === 1 ? "" : "s"}
                        {challenge.publishedAt &&
                          ` · published ${formatDate(challenge.publishedAt)}`}
                      </p>
                    </div>
                    <StatusBadge status={challenge.status} />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="space-y-3">
          <SectionHeader
            title="Pilot KPI health"
            icon={Target}
            description={
              health
                ? `${health.met} of ${health.assessable} measured KPIs are meeting target.`
                : "No KPI results have been recorded yet."
            }
            actions={
              <Link
                to="/gov/pilots"
                className="text-xs font-medium text-brand-700 hover:underline"
              >
                View all
              </Link>
            }
          />
          {pilots.length === 0 ? (
            <EmptyState
              title="No pilots yet"
              description="A pilot starts once a shortlisted startup is selected for a challenge."
            />
          ) : (
            <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
              {pilots.map((pilot) => {
                const pilotHealth = kpiHealth(pilot.kpis)
                return (
                  <li key={pilot.id}>
                    <Link
                      to={`/gov/pilots/${pilot.id}`}
                      className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-slate-50"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-slate-900">
                          {pilot.companyName}
                        </p>
                        <p className="mt-0.5 truncate text-xs text-slate-500">
                          {pilot.challengeTitle}
                        </p>
                      </div>
                      <div className="shrink-0 text-right">
                        <StatusBadge status={pilot.status} />
                        <p className="mt-1 text-[11px] tabular-nums text-slate-500">
                          {pilotHealth
                            ? `${pilotHealth.met}/${pilotHealth.assessable} KPIs met`
                            : "No KPI results"}
                        </p>
                      </div>
                    </Link>
                  </li>
                )
              })}
            </ul>
          )}
        </section>
      </div>
    </div>
  )
}
