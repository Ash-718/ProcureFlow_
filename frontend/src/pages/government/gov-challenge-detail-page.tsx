import { useCallback, useEffect, useState } from "react"
import { useParams } from "react-router-dom"
import { CheckCircle2, IndianRupee, Loader2, Rocket, Sparkles, Target } from "lucide-react"
import { ChallengeApi, MatchingApi, ProposalApi } from "@/api/endpoints"
import { apiErrorMessage } from "@/api/client"
import type { Challenge, MatchResultRow, Proposal } from "@/types"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { StatusBadge } from "@/components/ui/status-badge"
import { Badge } from "@/components/ui/badge"
import { ErrorState, LoadingState } from "@/components/ui/state-views"
import {
  MatchCandidateCard,
  MatchingSummary,
  type NormalizedMatch,
} from "@/components/match-candidate-card"
import { StartupProfileDialog } from "@/components/startup-profile-dialog"
import { PilotCreateDialog } from "@/components/pilot-create-dialog"
import { formatCurrencyInr, formatDate } from "@/lib/utils"

function toNormalized(row: MatchResultRow): NormalizedMatch {
  return {
    startupId: row.startupId, companyName: row.companyName, rank: row.rank, overallScore: row.overallScore,
    semanticSimilarity: row.semanticSimilarityScore, technologyMatch: row.technologyMatchScore,
    domainMatch: row.domainMatchScore, experienceScore: row.experienceScore, readinessScore: row.readinessScore,
    reasons: row.reasons, gaps: row.gaps,
  }
}

export function GovChallengeDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [challenge, setChallenge] = useState<Challenge | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [matches, setMatches] = useState<NormalizedMatch[] | null>(null)
  const [matchProvider, setMatchProvider] = useState<string | null>(null)
  // Returned by the run endpoint: how many startups were actually scored,
  // as opposed to how many are shown. Null when results were read back from
  // storage, since the stored rows do not carry the field.
  const [analysedCount, setAnalysedCount] = useState<number | null>(null)
  const [matching, setMatching] = useState(false)
  const [matchError, setMatchError] = useState<string | null>(null)

  const [proposals, setProposals] = useState<Proposal[] | null>(null)
  const [publishing, setPublishing] = useState(false)

  const [profileDialogId, setProfileDialogId] = useState<string | null>(null)
  const [pilotDialog, setPilotDialog] = useState<{ startupId: string; companyName: string } | null>(null)

  const load = useCallback(() => {
    if (!id) return
    setLoadError(null)
    ChallengeApi.get(id).then(setChallenge).catch((e) => setLoadError(apiErrorMessage(e)))
    ProposalApi.listForChallenge(id).then(setProposals).catch(() => setProposals([]))
    MatchingApi.results(id)
      .then((rows) => {
        if (rows.length > 0) {
          setMatches(rows.map(toNormalized))
          setMatchProvider(rows[0].aiProvider)
        }
      })
      .catch(() => {})
  }, [id])

  useEffect(load, [load])

  async function runMatching() {
    if (!id) return
    setMatching(true)
    setMatchError(null)
    try {
      const response = await MatchingApi.run(id)
      setMatches(
        response.results.map((r) => ({
          startupId: r.startupId, companyName: r.companyName, rank: r.rank, overallScore: r.overallScore,
          semanticSimilarity: r.componentScores.semanticSimilarity, technologyMatch: r.componentScores.technologyMatch,
          domainMatch: r.componentScores.domainMatch, experienceScore: r.componentScores.experienceScore,
          readinessScore: r.componentScores.readinessScore, reasons: r.reasons, gaps: r.gaps,
        }))
      )
      setMatchProvider(response.aiProvider)
      setAnalysedCount(response.totalCandidatesConsidered)
      setChallenge((c) => (c ? { ...c, status: "MATCHING" } : c))
    } catch (err) {
      setMatchError(apiErrorMessage(err))
    } finally {
      setMatching(false)
    }
  }

  async function publish() {
    if (!id) return
    setPublishing(true)
    try {
      const updated = await ChallengeApi.publish(id)
      setChallenge(updated)
    } catch (err) {
      setLoadError(apiErrorMessage(err))
    } finally {
      setPublishing(false)
    }
  }

  async function setProposalStatus(proposalId: string, status: "SHORTLISTED" | "REJECTED") {
    const updated = await ProposalApi.updateStatus(proposalId, status)
    setProposals((prev) => prev?.map((p) => (p.id === proposalId ? updated : p)) ?? null)
  }

  if (loadError) return <ErrorState message={loadError} onRetry={load} />
  if (!challenge) return <LoadingState label="Loading challenge…" />

  const proposalByStartup = new Map((proposals ?? []).map((p) => [p.startupId, p]))

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="mb-1 flex items-center gap-2">
            <h1 className="text-xl font-bold text-slate-900">{challenge.title}</h1>
            <StatusBadge status={challenge.status} />
          </div>
          <p className="text-sm text-slate-500">{challenge.departmentName} · {challenge.domain}</p>
        </div>
        {challenge.status === "DRAFT" && (
          <Button onClick={publish} disabled={publishing}>
            {publishing && <Loader2 className="h-4 w-4 animate-spin" />}
            Publish challenge
          </Button>
        )}
      </div>

      <Card>
        <CardContent className="grid gap-6 p-5 md:grid-cols-3">
          <div className="md:col-span-2 space-y-4">
            <div>
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">Problem statement</p>
              <p className="text-sm text-slate-700">{challenge.problemStatement}</p>
            </div>
            {challenge.outcomesExpected && (
              <div>
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">Expected outcomes</p>
                <p className="text-sm text-slate-700">{challenge.outcomesExpected}</p>
              </div>
            )}
            {challenge.desiredTechnology && (
              <div>
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">Desired technology</p>
                <div className="flex flex-wrap gap-1.5">
                  {challenge.desiredTechnology.split(",").map((t) => (
                    <Badge key={t} variant="brand">{t.trim()}</Badge>
                  ))}
                </div>
              </div>
            )}
            <div>
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">Requirements</p>
              <ul className="space-y-1">
                {challenge.requirements.map((r) => (
                  <li key={r.id} className="flex items-start gap-1.5 text-sm text-slate-600">
                    <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
                    {r.description} {r.mandatory && <span className="text-xs text-slate-400">(mandatory · {r.requirementType})</span>}
                  </li>
                ))}
                {challenge.requirements.length === 0 && <p className="text-sm text-slate-400">None specified.</p>}
              </ul>
            </div>
          </div>
          <div className="space-y-4">
            {challenge.budgetRange && (
              <div className="flex items-center gap-2 text-sm text-slate-600">
                <IndianRupee className="h-4 w-4 text-slate-400" /> {challenge.budgetRange}
              </div>
            )}
            {challenge.timelineDays && (
              <div className="flex items-center gap-2 text-sm text-slate-600">
                <Target className="h-4 w-4 text-slate-400" /> {challenge.timelineDays} day timeline
              </div>
            )}
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">KPIs</p>
              <div className="space-y-2">
                {challenge.kpis.map((k) => (
                  <div key={k.id} className="rounded-lg bg-slate-50 px-3 py-2 text-sm">
                    <p className="font-medium text-slate-700">{k.kpiName}</p>
                    <p className="text-xs text-slate-500">Target: {k.targetValue ?? "—"} {k.unit}</p>
                  </div>
                ))}
                {challenge.kpis.length === 0 && <p className="text-sm text-slate-400">None specified.</p>}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {challenge.status !== "DRAFT" && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0">
            <div>
              <CardTitle className="flex items-center gap-2"><Sparkles className="h-4 w-4 text-brand-500" /> AI Startup Matching</CardTitle>
              <p className="text-xs text-slate-500">
                Scores every startup on the platform against this challenge.
              </p>
            </div>
            <Button onClick={runMatching} disabled={matching}>
              {matching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
              {matches ? "Re-run matching" : "Find Suitable Startups"}
            </Button>
          </CardHeader>
          <CardContent className="space-y-4">
            {matching && <LoadingState label="AI is scoring every startup against this challenge…" />}
            {matchError && <ErrorState message={matchError} onRetry={runMatching} />}
            {!matching && !matchError && matches !== null && matches.length > 0 && (
              <MatchingSummary
                analysed={analysedCount}
                shown={matches.length}
                provider={matchProvider}
              />
            )}
            {!matching && !matchError && matches === null && (
              <p className="py-6 text-center text-sm text-slate-400">
                Click "Find Suitable Startups" to run the AI matching pipeline against the startup database.
              </p>
            )}
            {!matching && matches?.map((m) => (
              <MatchCandidateCard
                key={m.startupId}
                match={m}
                onViewProfile={setProfileDialogId}
                actions={
                  proposalByStartup.has(m.startupId) ? (
                    <Badge variant="outline">Has submitted a proposal</Badge>
                  ) : (
                    <Badge variant="neutral">No proposal yet</Badge>
                  )
                }
              />
            ))}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Rocket className="h-4 w-4 text-brand-500" /> Proposals</CardTitle>
        </CardHeader>
        <CardContent>
          {proposals === null && <LoadingState label="Loading proposals…" />}
          {proposals?.length === 0 && <p className="py-6 text-center text-sm text-slate-400">No proposals submitted yet.</p>}
          {proposals && proposals.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-400">
                    <th className="pb-2 pr-4">Startup</th>
                    <th className="pb-2 pr-4">Cost estimate</th>
                    <th className="pb-2 pr-4">Timeline</th>
                    <th className="pb-2 pr-4">Submitted</th>
                    <th className="pb-2 pr-4">Status</th>
                    <th className="pb-2">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {proposals.map((p) => (
                    <tr key={p.id} className="border-b border-slate-100 last:border-0">
                      <td className="py-2.5 pr-4 font-medium text-slate-800">{p.companyName}</td>
                      <td className="py-2.5 pr-4 text-slate-600">{formatCurrencyInr(p.costEstimate)}</td>
                      <td className="py-2.5 pr-4 text-slate-600">{p.timelineEstimateDays ? `${p.timelineEstimateDays}d` : "—"}</td>
                      <td className="py-2.5 pr-4 text-slate-500">{formatDate(p.submittedAt)}</td>
                      <td className="py-2.5 pr-4"><StatusBadge status={p.status} /></td>
                      <td className="py-2.5">
                        <div className="flex gap-2">
                          {(p.status === "SUBMITTED" || p.status === "UNDER_REVIEW") && (
                            <>
                              <Button size="sm" variant="success" onClick={() => setProposalStatus(p.id, "SHORTLISTED")}>Shortlist</Button>
                              <Button size="sm" variant="outline" onClick={() => setProposalStatus(p.id, "REJECTED")}>Reject</Button>
                            </>
                          )}
                          {p.status === "SHORTLISTED" && (
                            <Button size="sm" onClick={() => setPilotDialog({ startupId: p.startupId, companyName: p.companyName })}>
                              <Rocket className="h-3.5 w-3.5" /> Create pilot
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <StartupProfileDialog startupId={profileDialogId} open={!!profileDialogId} onOpenChange={(o) => !o && setProfileDialogId(null)} />
      {pilotDialog && (
        <PilotCreateDialog
          open={!!pilotDialog}
          onOpenChange={(o) => !o && setPilotDialog(null)}
          challengeId={challenge.id}
          startupId={pilotDialog.startupId}
          companyName={pilotDialog.companyName}
          challengeKpis={challenge.kpis}
        />
      )}
    </div>
  )
}
