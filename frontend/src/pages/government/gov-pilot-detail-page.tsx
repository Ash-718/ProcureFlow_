import { useCallback, useEffect, useState } from "react"
import { useParams } from "react-router-dom"
import { Flag, Loader2, Milestone, Target } from "lucide-react"
import { PilotApi } from "@/api/endpoints"
import { apiErrorMessage } from "@/api/client"
import type { Pilot, Recommendation, RecommendationType } from "@/types"
import { Button } from "@/components/ui/button"
import { PageHeader, SectionHeader } from "@/components/ui/page-header"
import { StatusBadge } from "@/components/ui/status-badge"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { ErrorState, LoadingState } from "@/components/ui/state-views"
import { StatCard, StatGrid } from "@/components/ui/stat-card"
import { DecisionPanel } from "@/components/decision-panel"
import { KpiPanel } from "@/components/kpi-panel"
import { kpiHealth } from "@/lib/kpi"
import { MilestoneTimeline } from "@/components/milestone-timeline"
import { WorkflowRail } from "@/components/workflow-rail"
import { formatCurrencyInr, formatDate } from "@/lib/utils"

/**
 * Pilot execution and outcome.
 *
 * Restructured around the question a department actually asks — "is this pilot
 * working?" — so KPI achievement and schedule adherence lead, and the
 * Scale/Modify/Reject decision is the conclusion rather than one card among
 * several.
 *
 * All behaviour is unchanged: the same six endpoints, the same guards, the
 * same payloads.
 */
export function GovPilotDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [pilot, setPilot] = useState<Pilot | null>(null)
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [completing, setCompleting] = useState(false)
  const [deciding, setDeciding] = useState(false)
  const [kpiInputs, setKpiInputs] = useState<Record<string, string>>({})
  const [savingKpi, setSavingKpi] = useState<string | null>(null)

  const load = useCallback(() => {
    if (!id) return
    setError(null)
    PilotApi.get(id)
      .then(setPilot)
      .catch((e) => setError(apiErrorMessage(e)))
    // A pilot only has a recommendation once completed; a 404 here is normal.
    PilotApi.recommendation(id)
      .then(setRecommendation)
      .catch(() => setRecommendation(null))
  }, [id])

  useEffect(load, [load])

  async function updateMilestone(milestoneId: string, status: string) {
    if (!id) return
    setActionError(null)
    try {
      setPilot(
        await PilotApi.updateMilestone(
          id,
          milestoneId,
          status,
          status === "DONE" ? new Date().toISOString().slice(0, 10) : undefined,
        ),
      )
    } catch (err) {
      setActionError(apiErrorMessage(err))
    }
  }

  async function submitKpiResult(kpiId: string) {
    const raw = kpiInputs[kpiId]
    if (!id || !raw?.trim()) return
    const value = Number(raw)
    if (Number.isNaN(value)) {
      setActionError("Enter a number for the KPI reading.")
      return
    }
    setActionError(null)
    setSavingKpi(kpiId)
    try {
      setPilot(await PilotApi.addKpiResult(id, kpiId, value))
      setKpiInputs((previous) => ({ ...previous, [kpiId]: "" }))
    } catch (err) {
      setActionError(apiErrorMessage(err))
    } finally {
      setSavingKpi(null)
    }
  }

  async function completePilot() {
    if (!id) return
    setActionError(null)
    setCompleting(true)
    try {
      setPilot(await PilotApi.complete(id, "COMPLETED"))
      setRecommendation(await PilotApi.recommendation(id))
    } catch (err) {
      setActionError(apiErrorMessage(err))
    } finally {
      setCompleting(false)
    }
  }

  async function decide(finalDecision: RecommendationType) {
    if (!id) return
    setActionError(null)
    setDeciding(true)
    try {
      setRecommendation(await PilotApi.decide(id, finalDecision))
    } catch (err) {
      setActionError(apiErrorMessage(err))
    } finally {
      setDeciding(false)
    }
  }

  if (error) return <ErrorState message={error} onRetry={load} />
  if (!pilot) return <LoadingState label="Loading pilot…" />

  const health = kpiHealth(pilot.kpis)
  const delayed = pilot.milestones.filter((m) => m.status === "DELAYED").length
  const doneMilestones = pilot.milestones.filter((m) => m.status === "DONE").length
  const editable = pilot.status === "ACTIVE"

  return (
    <div className="space-y-7">
      <PageHeader
        breadcrumbs={[{ label: "Pilots", to: "/gov/pilots" }, { label: pilot.companyName }]}
        title={pilot.challengeTitle}
        description={`${pilot.companyName} · ${formatDate(pilot.startDate)}${
          pilot.endDate ? ` to ${formatDate(pilot.endDate)}` : ""
        }`}
        meta={<StatusBadge status={pilot.status} />}
        actions={
          editable && (
            <Button onClick={completePilot} disabled={completing}>
              {completing ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Flag className="h-4 w-4" />
              )}
              Complete pilot
            </Button>
          )
        }
      />

      <WorkflowRail current={pilot.status === "ACTIVE" ? "KPI" : "DECISION"} />

      {actionError && <ErrorState message={actionError} />}

      <StatGrid>
        <StatCard
          label="KPIs meeting target"
          value={health ? `${health.met}/${health.assessable}` : "—"}
          hint={health ? "Based on the latest recorded reading" : "No readings recorded yet"}
          icon={Target}
          tone={health && health.met === health.assessable ? "success" : "neutral"}
        />
        <StatCard
          label="Milestones complete"
          value={`${doneMilestones}/${pilot.milestones.length}`}
          hint={delayed > 0 ? `${delayed} delayed` : "None delayed"}
          icon={Milestone}
          tone={delayed > 0 ? "warning" : "neutral"}
        />
        <StatCard
          label="Contract value"
          value={pilot.contract ? formatCurrencyInr(pilot.contract.contractValue) : "—"}
          hint={pilot.contract ? `Contract ${pilot.contract.status}` : "No formal contract"}
        />
        <StatCard
          label="Outcome"
          value={
            recommendation
              ? (recommendation.finalDecision ?? recommendation.recommendation)
              : "In progress"
          }
          hint={
            recommendation
              ? recommendation.finalDecision
                ? "Decision recorded"
                : "Awaiting department decision"
              : "Complete the pilot to generate a recommendation"
          }
          tone={recommendation && !recommendation.finalDecision ? "warning" : "neutral"}
        />
      </StatGrid>

      {/* The decision leads once it exists — it is the point of the pilot. */}
      {recommendation && (
        <section className="space-y-3">
          <SectionHeader
            title="Scale, modify or reject"
            description="The system's assessment and the department's decision are recorded separately."
          />
          <DecisionPanel
            recommendation={recommendation}
            action={
              recommendation.finalDecision === null && (
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" variant="success" disabled={deciding} onClick={() => decide("SCALE")}>
                    Record: Scale
                  </Button>
                  <Button size="sm" variant="outline" disabled={deciding} onClick={() => decide("MODIFY")}>
                    Record: Modify
                  </Button>
                  <Button size="sm" variant="danger" disabled={deciding} onClick={() => decide("REJECT")}>
                    Record: Reject
                  </Button>
                </div>
              )
            }
          />
        </section>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="space-y-3">
          <SectionHeader
            title="KPI tracking"
            icon={Target}
            description="Each reading is appended to the KPI's history; earlier readings are retained."
          />
          <KpiPanel kpis={pilot.kpis} />

          {editable && pilot.kpis.length > 0 && (
            <div className="space-y-2 rounded-lg border border-slate-200 bg-white p-4">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                Record a reading
              </p>
              {pilot.kpis.map((kpi) => (
                <div key={kpi.id} className="flex items-center gap-2">
                  <label htmlFor={`kpi-${kpi.id}`} className="min-w-0 flex-1 truncate text-sm text-slate-700">
                    {kpi.kpiName}
                  </label>
                  <Input
                    id={`kpi-${kpi.id}`}
                    type="number"
                    className="w-24"
                    placeholder={kpi.unit ?? "Value"}
                    value={kpiInputs[kpi.id] ?? ""}
                    onChange={(event) =>
                      setKpiInputs((previous) => ({ ...previous, [kpi.id]: event.target.value }))
                    }
                  />
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={savingKpi === kpi.id || !kpiInputs[kpi.id]?.trim()}
                    onClick={() => submitKpiResult(kpi.id)}
                  >
                    {savingKpi === kpi.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Record"}
                  </Button>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="space-y-3">
          <SectionHeader title="Milestones" icon={Milestone} />
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <MilestoneTimeline milestones={pilot.milestones} />
          </div>

          {editable && pilot.milestones.length > 0 && (
            <div className="space-y-2 rounded-lg border border-slate-200 bg-white p-4">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                Update status
              </p>
              {pilot.milestones.map((milestone) => (
                <div key={milestone.id} className="flex items-center gap-2">
                  <span className="min-w-0 flex-1 truncate text-sm text-slate-700">
                    {milestone.title}
                  </span>
                  <Select
                    value={milestone.status}
                    onValueChange={(value) => updateMilestone(milestone.id, value)}
                  >
                    <SelectTrigger className="w-36" aria-label={`Status for ${milestone.title}`}>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="PENDING">Pending</SelectItem>
                      <SelectItem value="IN_PROGRESS">In progress</SelectItem>
                      <SelectItem value="DONE">Done</SelectItem>
                      <SelectItem value="DELAYED">Delayed</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              ))}
            </div>
          )}

          {pilot.contract && (
            <div className="rounded-lg border border-slate-200 bg-white p-4">
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
                Contract
              </p>
              <dl className="space-y-1.5 text-sm">
                {[
                  ["Value", formatCurrencyInr(pilot.contract.contractValue)],
                  ["Payment terms", pilot.contract.paymentTerms ?? "—"],
                  ["IP terms", pilot.contract.ipTerms ?? "—"],
                  ["Data terms", pilot.contract.dataTerms ?? "—"],
                ].map(([label, value]) => (
                  <div key={label} className="flex justify-between gap-4">
                    <dt className="shrink-0 text-slate-500">{label}</dt>
                    <dd className="text-right text-slate-800">{value}</dd>
                  </div>
                ))}
              </dl>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
