import { useCallback, useEffect, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { Loader2, Sparkles, UserSearch } from "lucide-react"
import { EvaluationApi, ProposalApi } from "@/api/endpoints"
import { apiErrorMessage } from "@/api/client"
import type { EvaluationCriterionItem, Proposal } from "@/types"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { StatusBadge } from "@/components/ui/status-badge"
import { Textarea } from "@/components/ui/textarea"
import { ErrorState, LoadingState } from "@/components/ui/state-views"
import { StartupProfileDialog } from "@/components/startup-profile-dialog"
import { formatCurrencyInr, formatDate } from "@/lib/utils"

export function ExpertEvaluatePage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [proposal, setProposal] = useState<Proposal | null>(null)
  const [criteria, setCriteria] = useState<EvaluationCriterionItem[] | null>(null)
  const [aiSummary, setAiSummary] = useState<string | null>(null)
  const [aiLoading, setAiLoading] = useState(true)
  const [scores, setScores] = useState<Record<string, string>>({})
  const [remarks, setRemarks] = useState<Record<string, string>>({})
  const [comments, setComments] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [showProfile, setShowProfile] = useState(false)

  const load = useCallback(() => {
    if (!id) return
    setError(null)
    ProposalApi.get(id).then(setProposal).catch((e) => setError(apiErrorMessage(e)))
    EvaluationApi.criteria(id).then(setCriteria).catch(() => setCriteria([]))
    setAiLoading(true)
    EvaluationApi.aiAnalysis(id)
      .then((r) => setAiSummary(r.summary))
      .catch(() => setAiSummary("AI-assisted analysis is temporarily unavailable — please evaluate using the proposal details and your own judgment."))
      .finally(() => setAiLoading(false))
  }, [id])
  useEffect(load, [load])

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!id || !criteria) return
    setSubmitting(true)
    setError(null)
    try {
      await EvaluationApi.submit(id, {
        comments: comments || undefined,
        scores: criteria.map((c) => ({
          criterionId: c.id, score: Number(scores[c.id] ?? 0), remarks: remarks[c.id] || undefined,
        })),
      })
      setSubmitted(true)
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  if (error && !proposal) return <ErrorState message={error} onRetry={load} />
  if (!proposal || !criteria) return <LoadingState label="Loading proposal…" />

  if (submitted) {
    return (
      <div className="mx-auto max-w-2xl py-16 text-center">
        <p className="mb-2 text-lg font-semibold text-slate-900">Evaluation submitted</p>
        <p className="mb-6 text-sm text-slate-500">Thanks — your scores have been recorded for {proposal.companyName}.</p>
        <Button onClick={() => navigate("/expert")}>Back to queue</Button>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <div className="mb-1 flex items-center gap-2">
          <h1 className="text-xl font-bold text-slate-900">{proposal.companyName}</h1>
          <StatusBadge status={proposal.status} />
        </div>
        <p className="text-sm text-slate-500">Proposal for "{proposal.challengeTitle}"</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            Proposal details
            <button onClick={() => setShowProfile(true)} className="flex items-center gap-1 text-xs font-medium text-brand-600 hover:underline">
              <UserSearch className="h-3.5 w-3.5" /> View startup profile
            </button>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <p className="text-slate-700">{proposal.summary}</p>
          {proposal.proposedApproach && <p className="text-slate-600">{proposal.proposedApproach}</p>}
          <div className="flex gap-6 text-xs text-slate-500">
            <span>Cost estimate: {formatCurrencyInr(proposal.costEstimate)}</span>
            <span>Timeline: {proposal.timelineEstimateDays ? `${proposal.timelineEstimateDays} days` : "—"}</span>
            <span>Submitted {formatDate(proposal.submittedAt)}</span>
          </div>
        </CardContent>
      </Card>

      <Card className="border-brand-200 bg-brand-50/30">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Sparkles className="h-4 w-4 text-brand-500" /> AI-Assisted Analysis</CardTitle>
        </CardHeader>
        <CardContent>
          {aiLoading ? (
            <p className="text-sm text-slate-400">Generating analysis from the same scoring model used for challenge-wide matching…</p>
          ) : (
            <p className="text-sm text-slate-700">{aiSummary}</p>
          )}
          <p className="mt-3 rounded-md bg-white px-3 py-2 text-xs text-slate-500">
            This is AI assistance to inform your review — the final scoring judgment is yours.
          </p>
        </CardContent>
      </Card>

      <form onSubmit={onSubmit}>
        <Card>
          <CardHeader><CardTitle>Your evaluation</CardTitle></CardHeader>
          <CardContent className="space-y-5">
            {criteria.map((c) => (
              <div key={c.id} className="space-y-2 border-b border-slate-100 pb-4 last:border-0">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium text-slate-700">{c.criterionName}</label>
                  <span className="text-xs text-slate-400">weight {Math.round(c.weight * 100)}%</span>
                </div>
                <input
                  type="range" min={0} max={Number(c.maxScore)} step={0.5}
                  value={scores[c.id] ?? "0"}
                  onChange={(e) => setScores((s) => ({ ...s, [c.id]: e.target.value }))}
                  className="w-full accent-brand-600"
                />
                <div className="flex items-center justify-between text-xs text-slate-500">
                  <span>0</span>
                  <span className="font-semibold text-slate-800">{scores[c.id] ?? "0"} / {c.maxScore}</span>
                  <span>{c.maxScore}</span>
                </div>
                <Textarea
                  rows={1} placeholder="Remarks (optional)"
                  value={remarks[c.id] ?? ""} onChange={(e) => setRemarks((r) => ({ ...r, [c.id]: e.target.value }))}
                />
              </div>
            ))}
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-slate-700">Overall comments</label>
              <Textarea rows={3} value={comments} onChange={(e) => setComments(e.target.value)} />
            </div>
            {error && <p className="rounded-md bg-danger-50 px-3 py-2 text-sm text-danger-700">{error}</p>}
            <Button type="submit" disabled={submitting}>
              {submitting && <Loader2 className="h-4 w-4 animate-spin" />} Submit evaluation
            </Button>
          </CardContent>
        </Card>
      </form>

      <StartupProfileDialog startupId={proposal.startupId} open={showProfile} onOpenChange={setShowProfile} />
    </div>
  )
}
