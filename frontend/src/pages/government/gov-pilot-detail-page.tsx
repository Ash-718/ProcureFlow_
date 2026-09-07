import { useCallback, useEffect, useState } from "react"
import { useParams } from "react-router-dom"
import { CheckCircle2, Flag, Loader2, Sparkles } from "lucide-react"
import { PilotApi } from "@/api/endpoints"
import { apiErrorMessage } from "@/api/client"
import type { Pilot, Recommendation } from "@/types"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { StatusBadge } from "@/components/ui/status-badge"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ComponentScoreBar } from "@/components/component-score-bar"
import { ErrorState, LoadingState } from "@/components/ui/state-views"
import { formatCurrencyInr, formatDate } from "@/lib/utils"

export function GovPilotDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [pilot, setPilot] = useState<Pilot | null>(null)
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [completing, setCompleting] = useState(false)
  const [kpiInputs, setKpiInputs] = useState<Record<string, string>>({})

  const load = useCallback(() => {
    if (!id) return
    setError(null)
    PilotApi.get(id).then(setPilot).catch((e) => setError(apiErrorMessage(e)))
    PilotApi.recommendation(id).then(setRecommendation).catch(() => setRecommendation(null))
  }, [id])
  useEffect(load, [load])

  async function updateMilestone(milestoneId: string, status: string) {
    if (!id) return
    const updated = await PilotApi.updateMilestone(id, milestoneId, status, status === "DONE" ? new Date().toISOString().slice(0, 10) : undefined)
    setPilot(updated)
  }

  async function submitKpiResult(kpiId: string) {
    if (!id || !kpiInputs[kpiId]) return
    const updated = await PilotApi.addKpiResult(id, kpiId, Number(kpiInputs[kpiId]))
    setPilot(updated)
    setKpiInputs((v) => ({ ...v, [kpiId]: "" }))
  }

  async function completePilot() {
    if (!id) return
    setCompleting(true)
    try {
      const updated = await PilotApi.complete(id, "COMPLETED")
      setPilot(updated)
      const rec = await PilotApi.recommendation(id)
      setRecommendation(rec)
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setCompleting(false)
    }
  }

  async function decide(finalDecision: string) {
    if (!id) return
    const updated = await PilotApi.decide(id, finalDecision)
    setRecommendation(updated)
  }

  if (error) return <ErrorState message={error} onRetry={load} />
  if (!pilot) return <LoadingState label="Loading pilot…" />

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="mb-1 flex items-center gap-2">
            <h1 className="text-xl font-bold text-slate-900">{pilot.challengeTitle}</h1>
            <StatusBadge status={pilot.status} />
          </div>
          <p className="text-sm text-slate-500">
            {pilot.companyName} · {formatDate(pilot.startDate)} {pilot.endDate && `→ ${formatDate(pilot.endDate)}`}
          </p>
        </div>
        {pilot.status === "ACTIVE" && (
          <Button onClick={completePilot} disabled={completing}>
            {completing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Flag className="h-4 w-4" />}
            Complete pilot
          </Button>
        )}
      </div>

      {pilot.contract && (
        <Card>
          <CardHeader><CardTitle>Contract</CardTitle></CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-3 text-sm">
            <div><p className="text-xs text-slate-400">Value</p><p className="font-medium text-slate-700">{formatCurrencyInr(pilot.contract.contractValue)}</p></div>
            <div><p className="text-xs text-slate-400">Payment terms</p><p className="font-medium text-slate-700">{pilot.contract.paymentTerms ?? "—"}</p></div>
            <div><p className="text-xs text-slate-400">Status</p><StatusBadge status={pilot.contract.status} /></div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle>Milestones</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {pilot.milestones.map((m) => (
            <div key={m.id} className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 p-3">
              <div>
                <p className="text-sm font-medium text-slate-700">{m.title}</p>
                <p className="text-xs text-slate-400">
                  Due {formatDate(m.dueDate)} {m.completionDate && `· Completed ${formatDate(m.completionDate)}`}
                </p>
              </div>
              <Select value={m.status} onValueChange={(v) => updateMilestone(m.id, v)} disabled={pilot.status !== "ACTIVE"}>
                <SelectTrigger className="w-36"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="PENDING">Pending</SelectItem>
                  <SelectItem value="IN_PROGRESS">In progress</SelectItem>
                  <SelectItem value="DONE">Done</SelectItem>
                  <SelectItem value="DELAYED">Delayed</SelectItem>
                </SelectContent>
              </Select>
            </div>
          ))}
          {pilot.milestones.length === 0 && <p className="text-sm text-slate-400">No milestones defined.</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>KPI tracking</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {pilot.kpis.map((k) => (
            <div key={k.id} className="rounded-lg border border-slate-200 p-3">
              <div className="mb-1 flex items-center justify-between">
                <p className="text-sm font-medium text-slate-700">{k.kpiName}</p>
                <p className="text-xs text-slate-400">Target: {k.targetValue ?? "—"} {k.unit}</p>
              </div>
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm text-slate-600">
                  Latest: {k.latestRecordedValue !== null ? `${k.latestRecordedValue} ${k.unit ?? ""}` : "Not recorded yet"}
                </p>
                {pilot.status === "ACTIVE" && (
                  <div className="flex gap-2">
                    <Input
                      type="number" className="w-28" placeholder="Value"
                      value={kpiInputs[k.id] ?? ""}
                      onChange={(e) => setKpiInputs((v) => ({ ...v, [k.id]: e.target.value }))}
                    />
                    <Button size="sm" variant="outline" onClick={() => submitKpiResult(k.id)}>Record</Button>
                  </div>
                )}
              </div>
            </div>
          ))}
          {pilot.kpis.length === 0 && <p className="text-sm text-slate-400">No KPIs defined.</p>}
        </CardContent>
      </Card>

      {recommendation && (
        <Card className="border-brand-200">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-brand-500" /> AI-Assisted Recommendation
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-3">
              <StatusBadge status={recommendation.recommendation} />
              <span className="text-sm text-slate-500">generated {formatDate(recommendation.generatedAt)}</span>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <ComponentScoreBar label="Cost efficiency" value={recommendation.costScore * 100} />
              <ComponentScoreBar label="Performance" value={recommendation.performanceScore * 100} />
              <ComponentScoreBar label="Impact" value={recommendation.impactScore * 100} />
            </div>
            <p className="rounded-lg bg-slate-50 p-3 text-sm text-slate-600">{recommendation.rationaleText}</p>

            <div className="rounded-lg border border-warning-200 bg-warning-50 p-3 text-xs text-warning-800">
              This recommendation is AI-generated from pilot KPI and milestone data. The final call is made by an
              authorized government official below.
            </div>

            {recommendation.finalDecision ? (
              <div className="flex items-center gap-2 text-sm text-slate-600">
                <CheckCircle2 className="h-4 w-4 text-success-600" />
                Final decision: <StatusBadge status={recommendation.finalDecision} /> by {recommendation.reviewedByName} on {formatDate(recommendation.decidedAt)}
              </div>
            ) : (
              <div className="flex gap-2">
                <Button size="sm" variant="success" onClick={() => decide("SCALE")}>Approve: Scale</Button>
                <Button size="sm" variant="outline" onClick={() => decide("MODIFY")}>Approve: Modify</Button>
                <Button size="sm" variant="danger" onClick={() => decide("REJECT")}>Approve: Reject</Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
