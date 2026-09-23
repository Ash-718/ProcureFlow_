import { useEffect, useState } from "react"
import { Loader2, Plus, Sparkles } from "lucide-react"
import { StartupApi } from "@/api/endpoints"
import { apiErrorMessage } from "@/api/client"
import type { Startup } from "@/types"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { ErrorState, LoadingState } from "@/components/ui/state-views"

export function StartupProfilePage() {
  const [startup, setStartup] = useState<Startup | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [savedNotice, setSavedNotice] = useState(false)

  const [form, setForm] = useState({
    companyName: "", dpiitNumber: "", foundedYear: "", teamSize: "", city: "", state: "",
    description: "", readinessScore: "50",
  })

  const [capTech, setCapTech] = useState("")
  const [capDomain, setCapDomain] = useState("")
  const [capLevel, setCapLevel] = useState("3")

  const [projTitle, setProjTitle] = useState("")
  const [projDomain, setProjDomain] = useState("")
  const [projStack, setProjStack] = useState("")
  const [projClient, setProjClient] = useState<"GOVERNMENT" | "PRIVATE">("PRIVATE")
  const [projOutcome, setProjOutcome] = useState("")
  const [projYear, setProjYear] = useState("")

  function load() {
    setError(null)
    StartupApi.me()
      .then((s) => {
        setStartup(s)
        setForm({
          companyName: s.companyName, dpiitNumber: s.dpiitNumber ?? "",
          foundedYear: s.foundedYear ? String(s.foundedYear) : "", teamSize: s.teamSize ? String(s.teamSize) : "",
          city: s.city ?? "", state: s.state ?? "", description: s.description ?? "",
          readinessScore: String(s.readinessScore),
        })
      })
      .catch((e) => setError(apiErrorMessage(e)))
  }
  useEffect(load, [])

  async function saveProfile(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const updated = await StartupApi.updateMe({
        companyName: form.companyName,
        dpiitNumber: form.dpiitNumber || undefined,
        foundedYear: form.foundedYear ? Number(form.foundedYear) : undefined,
        teamSize: form.teamSize ? Number(form.teamSize) : undefined,
        city: form.city || undefined,
        state: form.state || undefined,
        description: form.description || undefined,
        readinessScore: Number(form.readinessScore),
      })
      setStartup(updated)
      setSavedNotice(true)
      setTimeout(() => setSavedNotice(false), 2500)
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  async function addCapability(e: React.FormEvent) {
    e.preventDefault()
    if (!capTech || !capDomain) return
    const updated = await StartupApi.addCapability({ technologyTag: capTech, domainTag: capDomain, proficiencyLevel: Number(capLevel) })
    setStartup(updated)
    setCapTech(""); setCapDomain(""); setCapLevel("3")
  }

  async function addProject(e: React.FormEvent) {
    e.preventDefault()
    if (!projTitle || !projDomain) return
    const updated = await StartupApi.addProject({
      title: projTitle, domain: projDomain, technologyStack: projStack || undefined,
      clientType: projClient, outcomeSummary: projOutcome || undefined, year: projYear ? Number(projYear) : undefined,
    })
    setStartup(updated)
    setProjTitle(""); setProjDomain(""); setProjStack(""); setProjOutcome(""); setProjYear("")
  }

  if (error) return <ErrorState message={error} onRetry={load} />
  if (!startup) return <LoadingState label="Loading your profile…" />

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Company Profile</h1>
        <p className="text-sm text-slate-500">
          Keep this current — capabilities and past projects directly feed the AI matching engine that surfaces you to government challenges.
        </p>
      </div>

      <Card>
        <CardHeader><CardTitle>Basics</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={saveProfile} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label>Company name</Label>
                <Input required value={form.companyName} onChange={(e) => setForm((f) => ({ ...f, companyName: e.target.value }))} />
              </div>
              <div className="space-y-1.5">
                <Label>DPIIT number</Label>
                <Input value={form.dpiitNumber} onChange={(e) => setForm((f) => ({ ...f, dpiitNumber: e.target.value }))} />
              </div>
              <div className="space-y-1.5">
                <Label>Founded year</Label>
                <Input type="number" value={form.foundedYear} onChange={(e) => setForm((f) => ({ ...f, foundedYear: e.target.value }))} />
              </div>
              <div className="space-y-1.5">
                <Label>Team size</Label>
                <Input type="number" value={form.teamSize} onChange={(e) => setForm((f) => ({ ...f, teamSize: e.target.value }))} />
              </div>
              <div className="space-y-1.5">
                <Label>City</Label>
                <Input value={form.city} onChange={(e) => setForm((f) => ({ ...f, city: e.target.value }))} />
              </div>
              <div className="space-y-1.5">
                <Label>State</Label>
                <Input value={form.state} onChange={(e) => setForm((f) => ({ ...f, state: e.target.value }))} />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Description</Label>
              <Textarea rows={3} value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} />
            </div>
            <div className="space-y-1.5">
              <Label>Pilot readiness self-assessment: {form.readinessScore}/100</Label>
              <input
                type="range" min={0} max={100} value={form.readinessScore}
                onChange={(e) => setForm((f) => ({ ...f, readinessScore: e.target.value }))}
                className="w-full accent-brand-600"
              />
              <p className="text-xs text-slate-400">Factored into the AI matching formula's readiness component (15% weight).</p>
            </div>
            {error && <p className="rounded-md bg-danger-50 px-3 py-2 text-sm text-danger-700">{error}</p>}
            <div className="flex items-center gap-3">
              <Button type="submit" disabled={saving}>
                {saving && <Loader2 className="h-4 w-4 animate-spin" />} Save profile
              </Button>
              {savedNotice && <span className="text-sm text-success-600">Saved — recomputing your AI match profile.</span>}
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Capabilities</CardTitle>
          <CardDescription>Technology + domain tags with a proficiency level (1-5) — this drives the technology and domain match scores.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {startup.capabilities.map((c) => (
              <Badge key={c.id} variant="brand">{c.technologyTag} · {c.domainTag} (L{c.proficiencyLevel})</Badge>
            ))}
            {startup.capabilities.length === 0 && <p className="text-sm text-slate-400">No capabilities added yet.</p>}
          </div>
          <form onSubmit={addCapability} className="grid gap-2 sm:grid-cols-[1fr_1fr_100px_auto]">
            <Input placeholder="Technology, e.g. Computer Vision" value={capTech} onChange={(e) => setCapTech(e.target.value)} />
            <Input placeholder="Domain, e.g. smart-mobility" value={capDomain} onChange={(e) => setCapDomain(e.target.value)} />
            <Select value={capLevel} onValueChange={setCapLevel}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {[1, 2, 3, 4, 5].map((v) => <SelectItem key={v} value={String(v)}>Level {v}</SelectItem>)}
              </SelectContent>
            </Select>
            <Button type="submit" size="sm"><Plus className="h-4 w-4" /> Add</Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Past projects</CardTitle>
          <CardDescription>Especially government-sector delivery history — it's the strongest signal in the experience score.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            {startup.projects.map((p) => (
              <div key={p.id} className="rounded-lg border border-slate-200 p-3 text-sm">
                <div className="flex items-center justify-between">
                  <p className="font-medium text-slate-800">{p.title}</p>
                  <Badge variant={p.clientType === "GOVERNMENT" ? "success" : "outline"}>
                    {p.clientType === "GOVERNMENT" ? "Govt client" : "Private client"}
                  </Badge>
                </div>
                <p className="text-xs text-slate-500">{p.domain} {p.year && `· ${p.year}`}</p>
              </div>
            ))}
            {startup.projects.length === 0 && <p className="text-sm text-slate-400">No past projects added yet.</p>}
          </div>
          <form onSubmit={addProject} className="space-y-2 rounded-lg border border-dashed border-slate-300 p-3">
            <div className="grid gap-2 sm:grid-cols-2">
              <Input placeholder="Project title" value={projTitle} onChange={(e) => setProjTitle(e.target.value)} />
              <Input placeholder="Domain" value={projDomain} onChange={(e) => setProjDomain(e.target.value)} />
              <Input placeholder="Technology stack" value={projStack} onChange={(e) => setProjStack(e.target.value)} />
              <Input type="number" placeholder="Year" value={projYear} onChange={(e) => setProjYear(e.target.value)} />
            </div>
            <Textarea placeholder="Outcome summary" rows={2} value={projOutcome} onChange={(e) => setProjOutcome(e.target.value)} />
            <div className="flex items-center gap-2">
              <Select value={projClient} onValueChange={(v) => setProjClient(v as "GOVERNMENT" | "PRIVATE")}>
                <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="PRIVATE">Private client</SelectItem>
                  <SelectItem value="GOVERNMENT">Government client</SelectItem>
                </SelectContent>
              </Select>
              <Button type="submit" size="sm"><Sparkles className="h-4 w-4" /> Add project</Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
