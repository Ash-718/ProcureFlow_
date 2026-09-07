import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { Loader2, Plus, Sparkles, Trash2 } from "lucide-react"
import { ChallengeApi, KnowledgeBaseApi } from "@/api/endpoints"
import { apiErrorMessage } from "@/api/client"
import type { ChallengeDraft, RequirementType, SimilarPilotMatch } from "@/types"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { StatusBadge } from "@/components/ui/status-badge"

const DOMAIN_SUGGESTIONS = [
  "smart-mobility", "agri-tech", "health-tech", "waste-management",
  "cybersecurity", "fintech-for-gov", "edtech",
]

interface RequirementRow { requirementType: RequirementType; description: string; mandatory: boolean }
interface KpiRow { kpiName: string; targetValue: string; unit: string; weight: string }

export function GovChallengeFormPage() {
  const navigate = useNavigate()
  const [title, setTitle] = useState("")
  const [problemStatement, setProblemStatement] = useState("")
  const [desiredTechnology, setDesiredTechnology] = useState("")
  const [domain, setDomain] = useState("")
  const [outcomesExpected, setOutcomesExpected] = useState("")
  const [budgetRange, setBudgetRange] = useState("")
  const [timelineDays, setTimelineDays] = useState("")

  const [requirements, setRequirements] = useState<RequirementRow[]>([
    { requirementType: "ELIGIBILITY", description: "DPIIT-recognized startup incorporated in India", mandatory: true },
  ])
  const [kpis, setKpis] = useState<KpiRow[]>([{ kpiName: "", targetValue: "", unit: "", weight: "1" }])

  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [similar, setSimilar] = useState<SimilarPilotMatch[] | null>(null)
  const [similarLoading, setSimilarLoading] = useState(false)

  async function checkSimilarPilots() {
    if (!title || !problemStatement || !domain) return
    setSimilarLoading(true)
    try {
      const response = await KnowledgeBaseApi.similarForDraft({
        title, problemStatement, domain, desiredTechnology: desiredTechnology || undefined,
        outcomesExpected: outcomesExpected || undefined,
      })
      setSimilar(response.results)
    } catch {
      setSimilar(null)
    } finally {
      setSimilarLoading(false)
    }
  }

  function updateRequirement(index: number, patch: Partial<RequirementRow>) {
    setRequirements((rows) => rows.map((r, i) => (i === index ? { ...r, ...patch } : r)))
  }
  function updateKpi(index: number, patch: Partial<KpiRow>) {
    setKpis((rows) => rows.map((r, i) => (i === index ? { ...r, ...patch } : r)))
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const draft: ChallengeDraft = {
        title, problemStatement, domain,
        desiredTechnology: desiredTechnology || undefined,
        outcomesExpected: outcomesExpected || undefined,
        budgetRange: budgetRange || undefined,
        timelineDays: timelineDays ? Number(timelineDays) : undefined,
        requirements: requirements.filter((r) => r.description.trim()),
        kpis: kpis
          .filter((k) => k.kpiName.trim())
          .map((k) => ({
            kpiName: k.kpiName,
            targetValue: k.targetValue ? Number(k.targetValue) : undefined,
            unit: k.unit || undefined,
            weight: k.weight ? Number(k.weight) : undefined,
          })),
      }
      const created = await ChallengeApi.create(draft)
      navigate(`/gov/challenges/${created.id}`)
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Problem-to-Challenge Converter</h1>
        <p className="text-sm text-slate-500">
          Turn a departmental problem into a structured challenge with KPIs and eligibility criteria that startups can discover and AI can match against.
        </p>
      </div>

      <form onSubmit={onSubmit} className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle>The problem</CardTitle>
              <CardDescription>Describe the problem in plain language — this is what AI matching reads.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="title">Challenge title</Label>
                <Input id="title" required value={title} onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g. AI-Based Pothole & Road Damage Detection System" />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="problem">Problem statement</Label>
                <Textarea id="problem" required rows={5} value={problemStatement}
                  onChange={(e) => setProblemStatement(e.target.value)}
                  placeholder="What is broken today, for whom, and why does it matter?" />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="domain">Domain</Label>
                  <Input id="domain" required list="domain-suggestions" value={domain}
                    onChange={(e) => setDomain(e.target.value)} placeholder="e.g. smart-mobility" />
                  <datalist id="domain-suggestions">
                    {DOMAIN_SUGGESTIONS.map((d) => <option key={d} value={d} />)}
                  </datalist>
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="tech">Desired technology (comma-separated)</Label>
                  <Input id="tech" value={desiredTechnology} onChange={(e) => setDesiredTechnology(e.target.value)}
                    placeholder="Computer Vision, IoT Sensors, GIS Mapping" />
                </div>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="outcomes">Expected outcomes</Label>
                <Textarea id="outcomes" rows={2} value={outcomesExpected} onChange={(e) => setOutcomesExpected(e.target.value)} />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="budget">Budget range</Label>
                  <Input id="budget" value={budgetRange} onChange={(e) => setBudgetRange(e.target.value)} placeholder="INR 50 lakh - 1.5 crore" />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="timeline">Timeline (days)</Label>
                  <Input id="timeline" type="number" min={0} value={timelineDays} onChange={(e) => setTimelineDays(e.target.value)} />
                </div>
              </div>
              <Button type="button" variant="outline" size="sm" onClick={checkSimilarPilots} disabled={!title || !problemStatement || !domain}>
                <Sparkles className="h-4 w-4" /> Check similar past pilots
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Eligibility & requirements</CardTitle>
              <CardDescription>Mandatory and optional criteria a startup must meet.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {requirements.map((row, i) => (
                <div key={i} className="flex items-start gap-2 rounded-lg border border-slate-200 p-3">
                  <div className="grid flex-1 gap-2 sm:grid-cols-[140px_1fr_auto]">
                    <Select value={row.requirementType} onValueChange={(v) => updateRequirement(i, { requirementType: v as RequirementType })}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="ELIGIBILITY">Eligibility</SelectItem>
                        <SelectItem value="TECHNICAL">Technical</SelectItem>
                        <SelectItem value="COMPLIANCE">Compliance</SelectItem>
                      </SelectContent>
                    </Select>
                    <Input value={row.description} onChange={(e) => updateRequirement(i, { description: e.target.value })}
                      placeholder="Requirement description" />
                    <label className="flex items-center gap-1.5 whitespace-nowrap text-sm text-slate-600">
                      <input type="checkbox" checked={row.mandatory} onChange={(e) => updateRequirement(i, { mandatory: e.target.checked })} />
                      Mandatory
                    </label>
                  </div>
                  <button type="button" onClick={() => setRequirements((rows) => rows.filter((_, idx) => idx !== i))}
                    className="mt-2 text-slate-400 hover:text-danger-600">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              ))}
              <Button type="button" variant="outline" size="sm"
                onClick={() => setRequirements((rows) => [...rows, { requirementType: "TECHNICAL", description: "", mandatory: true }])}>
                <Plus className="h-4 w-4" /> Add requirement
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>KPIs</CardTitle>
              <CardDescription>Measurable targets used later to track pilot performance.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {kpis.map((row, i) => (
                <div key={i} className="flex items-start gap-2 rounded-lg border border-slate-200 p-3">
                  <div className="grid flex-1 gap-2 sm:grid-cols-4">
                    <Input className="sm:col-span-2" value={row.kpiName} onChange={(e) => updateKpi(i, { kpiName: e.target.value })}
                      placeholder="KPI name, e.g. Defect Detection Accuracy" />
                    <Input type="number" value={row.targetValue} onChange={(e) => updateKpi(i, { targetValue: e.target.value })} placeholder="Target" />
                    <Input value={row.unit} onChange={(e) => updateKpi(i, { unit: e.target.value })} placeholder="Unit, e.g. percent" />
                  </div>
                  <button type="button" onClick={() => setKpis((rows) => rows.filter((_, idx) => idx !== i))}
                    className="mt-2 text-slate-400 hover:text-danger-600">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              ))}
              <Button type="button" variant="outline" size="sm"
                onClick={() => setKpis((rows) => [...rows, { kpiName: "", targetValue: "", unit: "", weight: "1" }])}>
                <Plus className="h-4 w-4" /> Add KPI
              </Button>
            </CardContent>
          </Card>

          {error && <p className="rounded-md bg-danger-50 px-3 py-2 text-sm text-danger-700">{error}</p>}

          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => navigate(-1)}>Cancel</Button>
            <Button type="submit" disabled={submitting}>
              {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
              Save as draft
            </Button>
          </div>
        </div>

        <div className="space-y-4">
          <Card className="sticky top-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><Sparkles className="h-4 w-4 text-brand-500" /> Similar past pilots</CardTitle>
              <CardDescription>AI-surfaced context from the knowledge base for this domain.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {similarLoading && <p className="text-sm text-slate-400">Searching knowledge base…</p>}
              {!similarLoading && similar === null && (
                <p className="text-sm text-slate-400">Fill in the title, problem statement and domain, then click "Check similar past pilots".</p>
              )}
              {!similarLoading && similar !== null && similar.length === 0 && (
                <p className="text-sm text-slate-400">No comparable past pilots found yet.</p>
              )}
              {!similarLoading && similar?.map((s) => (
                <div key={s.pilotId} className="rounded-lg border border-slate-200 p-3 text-sm">
                  <div className="mb-1 flex items-center justify-between gap-2">
                    <p className="font-medium text-slate-800">{s.challengeTitle}</p>
                    {s.success !== null && <StatusBadge status={String(s.success)} />}
                  </div>
                  <p className="mb-1 text-xs text-slate-500">{s.domain} · {s.similarity.toFixed(0)}% similar</p>
                  {s.outcomeSummary && <p className="line-clamp-3 text-xs text-slate-500">{s.outcomeSummary}</p>}
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </form>
    </div>
  )
}
