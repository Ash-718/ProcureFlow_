import { useCallback, useEffect, useState } from "react"
import { useParams } from "react-router-dom"
import { CheckCircle2, IndianRupee, Loader2, Send, Target } from "lucide-react"
import { ChallengeApi, ProposalApi } from "@/api/endpoints"
import { apiErrorMessage } from "@/api/client"
import type { Challenge, Proposal } from "@/types"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { StatusBadge } from "@/components/ui/status-badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { ErrorState, LoadingState } from "@/components/ui/state-views"

export function StartupChallengeDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [challenge, setChallenge] = useState<Challenge | null>(null)
  const [myProposal, setMyProposal] = useState<Proposal | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const [summary, setSummary] = useState("")
  const [approach, setApproach] = useState("")
  const [cost, setCost] = useState("")
  const [timeline, setTimeline] = useState("")

  const load = useCallback(() => {
    if (!id) return
    setError(null)
    ChallengeApi.get(id).then(setChallenge).catch((e) => setError(apiErrorMessage(e)))
    ProposalApi.listMine().then((mine) => setMyProposal(mine.find((p) => p.challengeId === id) ?? null)).catch(() => {})
  }, [id])
  useEffect(load, [load])

  async function submitProposal(e: React.FormEvent) {
    e.preventDefault()
    if (!id) return
    setSubmitting(true)
    setError(null)
    try {
      const proposal = await ProposalApi.submit(id, {
        summary, proposedApproach: approach || undefined,
        costEstimate: cost ? Number(cost) : undefined,
        timelineEstimateDays: timeline ? Number(timeline) : undefined,
      })
      setMyProposal(proposal)
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  if (error && !challenge) return <ErrorState message={error} onRetry={load} />
  if (!challenge) return <LoadingState label="Loading challenge…" />

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-900">{challenge.title}</h1>
        <p className="text-sm text-slate-500">{challenge.departmentName} · {challenge.domain}</p>
      </div>

      <Card>
        <CardContent className="space-y-4 p-5">
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
            <div className="flex flex-wrap gap-1.5">
              {challenge.desiredTechnology.split(",").map((t) => <Badge key={t} variant="brand">{t.trim()}</Badge>)}
            </div>
          )}
          <div className="flex flex-wrap gap-4 text-sm text-slate-600">
            {challenge.budgetRange && <span className="flex items-center gap-1"><IndianRupee className="h-4 w-4 text-slate-400" />{challenge.budgetRange}</span>}
            {challenge.timelineDays && <span className="flex items-center gap-1"><Target className="h-4 w-4 text-slate-400" />{challenge.timelineDays} days</span>}
          </div>
          <div>
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">Eligibility & requirements</p>
            <ul className="space-y-1">
              {challenge.requirements.map((r) => (
                <li key={r.id} className="flex items-start gap-1.5 text-sm text-slate-600">
                  <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" /> {r.description}
                </li>
              ))}
            </ul>
          </div>
          <div>
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">KPIs you'd be measured on</p>
            <div className="flex flex-wrap gap-2">
              {challenge.kpis.map((k) => (
                <span key={k.id} className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
                  {k.kpiName}: {k.targetValue ?? "—"} {k.unit}
                </span>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Your proposal</CardTitle></CardHeader>
        <CardContent>
          {myProposal ? (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <StatusBadge status={myProposal.status} />
                <span className="text-sm text-slate-500">submitted {new Date(myProposal.submittedAt).toLocaleDateString()}</span>
              </div>
              <p className="text-sm text-slate-700">{myProposal.summary}</p>
              {myProposal.proposedApproach && <p className="text-sm text-slate-600">{myProposal.proposedApproach}</p>}
            </div>
          ) : (
            <form onSubmit={submitProposal} className="space-y-4">
              <div className="space-y-1.5">
                <Label>Summary</Label>
                <Textarea required rows={3} value={summary} onChange={(e) => setSummary(e.target.value)}
                  placeholder="Why is your startup the right fit for this challenge?" />
              </div>
              <div className="space-y-1.5">
                <Label>Proposed approach</Label>
                <Textarea rows={3} value={approach} onChange={(e) => setApproach(e.target.value)} />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label>Cost estimate (INR)</Label>
                  <Input type="number" value={cost} onChange={(e) => setCost(e.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <Label>Timeline estimate (days)</Label>
                  <Input type="number" value={timeline} onChange={(e) => setTimeline(e.target.value)} />
                </div>
              </div>
              {error && <p className="rounded-md bg-danger-50 px-3 py-2 text-sm text-danger-700">{error}</p>}
              <Button type="submit" disabled={submitting}>
                {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                Submit proposal
              </Button>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
