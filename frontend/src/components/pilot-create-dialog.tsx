import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { Loader2, Plus, Trash2 } from "lucide-react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { PilotApi } from "@/api/endpoints"
import { apiErrorMessage } from "@/api/client"
import type { ChallengeKpi } from "@/types"

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  challengeId: string
  startupId: string
  companyName: string
  challengeKpis: ChallengeKpi[]
}

export function PilotCreateDialog({ open, onOpenChange, challengeId, startupId, companyName, challengeKpis }: Props) {
  const navigate = useNavigate()
  const [startDate, setStartDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [endDate, setEndDate] = useState("")
  const [milestones, setMilestones] = useState([{ title: "Kickoff & environment setup", dueDate: "" }])
  const [kpiTargets, setKpiTargets] = useState<Record<string, string>>({})
  const [contractValue, setContractValue] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const pilot = await PilotApi.create({
        challengeId, startupId, startDate, endDate: endDate || undefined,
        milestones: milestones.filter((m) => m.title.trim()).map((m) => ({ title: m.title, dueDate: m.dueDate || undefined })),
        kpis: challengeKpis.map((k) => ({
          kpiName: k.kpiName,
          targetValue: kpiTargets[k.id] ? Number(kpiTargets[k.id]) : (k.targetValue ?? undefined),
          unit: k.unit ?? undefined,
        })),
        contract: contractValue ? { contractValue: Number(contractValue) } : undefined,
      })
      onOpenChange(false)
      navigate(`/gov/pilots/${pilot.id}`)
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Create pilot with {companyName}</DialogTitle>
          <DialogDescription>Define milestones and KPI targets to track during the controlled pilot.</DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Start date</Label>
              <Input type="date" required value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>End date (optional)</Label>
              <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label>Contract value (INR, optional)</Label>
            <Input type="number" min={0} value={contractValue} onChange={(e) => setContractValue(e.target.value)} placeholder="8500000" />
          </div>

          <div className="space-y-2">
            <Label>Milestones</Label>
            {milestones.map((m, i) => (
              <div key={i} className="flex gap-2">
                <Input
                  className="flex-1" value={m.title}
                  onChange={(e) => setMilestones((rows) => rows.map((r, idx) => idx === i ? { ...r, title: e.target.value } : r))}
                  placeholder="Milestone title"
                />
                <Input
                  type="date" className="w-40" value={m.dueDate}
                  onChange={(e) => setMilestones((rows) => rows.map((r, idx) => idx === i ? { ...r, dueDate: e.target.value } : r))}
                />
                <button type="button" onClick={() => setMilestones((rows) => rows.filter((_, idx) => idx !== i))} className="text-slate-400 hover:text-danger-600">
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
            <Button type="button" variant="outline" size="sm" onClick={() => setMilestones((rows) => [...rows, { title: "", dueDate: "" }])}>
              <Plus className="h-4 w-4" /> Add milestone
            </Button>
          </div>

          {challengeKpis.length > 0 && (
            <div className="space-y-2">
              <Label>KPI targets (from the challenge — adjust if needed)</Label>
              {challengeKpis.map((k) => (
                <div key={k.id} className="flex items-center gap-2 text-sm">
                  <span className="flex-1 text-slate-600">{k.kpiName} {k.unit && `(${k.unit})`}</span>
                  <Input
                    type="number" className="w-28"
                    value={kpiTargets[k.id] ?? (k.targetValue !== null ? String(k.targetValue) : "")}
                    onChange={(e) => setKpiTargets((v) => ({ ...v, [k.id]: e.target.value }))}
                  />
                </div>
              ))}
            </div>
          )}

          {error && <p className="rounded-md bg-danger-50 px-3 py-2 text-sm text-danger-700">{error}</p>}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={submitting}>
              {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
              Create pilot
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
