import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { ArrowRight, ClipboardList, Rocket, Search, UserCircle2 } from "lucide-react"
import { ChallengeApi, PilotApi, ProposalApi, StartupApi } from "@/api/endpoints"
import { apiErrorMessage } from "@/api/client"
import type { Challenge, Pilot, Proposal, Startup } from "@/types"
import { Button } from "@/components/ui/button"
import { PageHeader, SectionHeader } from "@/components/ui/page-header"
import { StatCard, StatCardSkeleton, StatGrid } from "@/components/ui/stat-card"
import { StatusBadge } from "@/components/ui/status-badge"
import { EmptyState, ErrorState } from "@/components/ui/state-views"
import { Progress } from "@/components/ui/progress"
import { formatDate } from "@/lib/utils"

/**
 * Startup home — an opportunity marketplace view.
 *
 * All real data:
 *   GET /startups/me        -> profile, capabilities, projects
 *   GET /challenges         -> open opportunities (backend already filters
 *                              drafts out for this role)
 *   GET /proposals/mine     -> submissions and their status
 *   GET /pilots             -> pilots this startup is running
 *
 * Profile completeness is computed from fields the API actually returns, and
 * the checklist names each missing one — it is a real prompt to improve
 * matchability, not a decorative percentage.
 */

interface DashboardData {
  profile: Startup
  challenges: Challenge[]
  proposals: Proposal[]
  pilots: Pilot[]
}

/** Fields that materially affect AI matching or eligibility. */
function completeness(profile: Startup) {
  const checks: { label: string; done: boolean }[] = [
    { label: "Company description", done: Boolean(profile.description?.trim()) },
    { label: "At least one capability", done: profile.capabilities.length > 0 },
    { label: "At least one past project", done: profile.projects.length > 0 },
    { label: "DPIIT recognition number", done: Boolean(profile.dpiitNumber?.trim()) },
    { label: "Team size", done: profile.teamSize !== null },
    { label: "Location", done: Boolean(profile.city?.trim()) },
  ]
  const done = checks.filter((check) => check.done).length
  return { checks, done, total: checks.length, percent: Math.round((done / checks.length) * 100) }
}

export function StartupDashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    setError(null)
    setData(null)
    Promise.all([
      StartupApi.me(),
      ChallengeApi.list(),
      ProposalApi.listMine(),
      PilotApi.list(),
    ])
      .then(([profile, challenges, proposals, pilots]) =>
        setData({ profile, challenges, proposals, pilots }),
      )
      .catch((err) => setError(apiErrorMessage(err)))
  }, [])

  useEffect(load, [load])

  const header = (
    <PageHeader
      title={data ? data.profile.companyName : "Dashboard"}
      description="Government challenges you can bid for, and the status of everything you have submitted."
      actions={
        <Button asChild variant="outline">
          <Link to="/startup/challenges">
            <Search className="h-4 w-4" /> Browse challenges
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

  const { profile, challenges, proposals, pilots } = data
  const open = challenges.filter((challenge) =>
    ["PUBLISHED", "MATCHING"].includes(challenge.status),
  )
  const appliedIds = new Set(proposals.map((proposal) => proposal.challengeId))
  const notYetApplied = open.filter((challenge) => !appliedIds.has(challenge.id))
  const shortlisted = proposals.filter((proposal) => proposal.status === "SHORTLISTED")
  const activePilots = pilots.filter((pilot) => pilot.status === "ACTIVE")
  const profileState = completeness(profile)

  return (
    <div className="space-y-7">
      {header}

      <StatGrid>
        <StatCard
          label="Open challenges"
          value={open.length}
          hint={
            notYetApplied.length > 0
              ? `${notYetApplied.length} you have not applied to`
              : "You have applied to all of them"
          }
          icon={Search}
          to="/startup/challenges"
        />
        <StatCard
          label="Proposals submitted"
          value={proposals.length}
          hint={`${shortlisted.length} shortlisted`}
          icon={ClipboardList}
          to="/startup/proposals"
        />
        <StatCard
          label="Active pilots"
          value={activePilots.length}
          hint={`${pilots.length} pilot${pilots.length === 1 ? "" : "s"} overall`}
          icon={Rocket}
        />
        <StatCard
          label="Profile completeness"
          value={`${profileState.percent}%`}
          hint={`${profileState.done} of ${profileState.total} fields provided`}
          icon={UserCircle2}
          tone={profileState.percent < 100 ? "warning" : "success"}
          to="/startup/profile"
        />
      </StatGrid>

      {profileState.percent < 100 && (
        <section className="rounded-lg border border-slate-200 bg-white p-5">
          <SectionHeader
            title="Improve your matchability"
            description="The AI matches on your capabilities, past projects and readiness. Filling these in directly affects how you rank against a challenge."
            icon={UserCircle2}
            actions={
              <Button asChild size="sm" variant="outline">
                <Link to="/startup/profile">Edit profile</Link>
              </Button>
            }
          />
          <Progress value={profileState.percent} className="mt-4" />
          <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
            {profileState.checks.map((check) => (
              <li
                key={check.label}
                className={
                  check.done
                    ? "text-xs text-slate-400 line-through"
                    : "text-xs font-medium text-slate-700"
                }
              >
                {check.done ? "✓" : "○"} {check.label}
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="space-y-3">
          <SectionHeader
            title="Opportunities you have not applied to"
            icon={Search}
            actions={
              <Link
                to="/startup/challenges"
                className="text-xs font-medium text-brand-700 hover:underline"
              >
                Browse all
              </Link>
            }
          />
          {notYetApplied.length === 0 ? (
            <EmptyState
              title="Nothing new right now"
              description="You have submitted a proposal for every open challenge. New ones appear here as departments publish them."
            />
          ) : (
            <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
              {notYetApplied.slice(0, 5).map((challenge) => (
                <li key={challenge.id}>
                  <Link
                    to={`/startup/challenges/${challenge.id}`}
                    className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-slate-50"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-slate-900">
                        {challenge.title}
                      </p>
                      <p className="mt-0.5 truncate text-xs text-slate-500">
                        {challenge.departmentName} · {challenge.domain}
                      </p>
                    </div>
                    <ArrowRight className="h-4 w-4 shrink-0 text-slate-400" aria-hidden />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="space-y-3">
          <SectionHeader
            title="Your proposals"
            icon={ClipboardList}
            actions={
              <Link
                to="/startup/proposals"
                className="text-xs font-medium text-brand-700 hover:underline"
              >
                View all
              </Link>
            }
          />
          {proposals.length === 0 ? (
            <EmptyState
              title="No proposals yet"
              description="Open a challenge you can deliver and submit a proposal to be considered."
              action={
                <Button asChild size="sm">
                  <Link to="/startup/challenges">Browse challenges</Link>
                </Button>
              }
            />
          ) : (
            <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
              {proposals.slice(0, 5).map((proposal) => (
                <li
                  key={proposal.id}
                  className="flex items-center gap-3 px-4 py-3"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-slate-900">
                      {proposal.challengeTitle}
                    </p>
                    <p className="mt-0.5 text-xs text-slate-500">
                      Submitted {formatDate(proposal.submittedAt)}
                    </p>
                  </div>
                  <StatusBadge status={proposal.status} />
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  )
}
