import { useEffect, useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { describeError, Empty, ErrorNote, Field, MissingFields, Section } from '@/components/common'
import { api } from '@/lib/api'
import type {
  Analysis,
  BarrierFlag,
  Challenge,
  Kpi,
  Pilot,
  PriorPilot,
  Proposal,
  Recommendation,
} from '@/types'

const BARRIER_CODES = [
  { code: 'TURNOVER_FLOOR', detail: 'Average annual turnover of at least Rs 5 crore' },
  { code: 'YEARS_IN_BUSINESS', detail: 'At least 5 years in continuous business' },
  { code: 'PRIOR_GOVERNMENT_PROJECTS', detail: 'Two similar completed government projects' },
  { code: 'OTHER', detail: 'Must hold a valid ISO 27001 certificate' },
]

const DECLINE_CODES = [
  'STRONGER_ALTERNATIVE_SELECTED',
  'CAPABILITY_MISMATCH',
  'BELOW_TECHNICAL_SCORE_THRESHOLD',
  'KPI_TARGETS_NOT_ADDRESSED',
  'DEPLOYMENT_READINESS_INSUFFICIENT',
  'SECURITY_COMPLIANCE_GAP',
  'INCOMPLETE_SUBMISSION',
]

export function GovernmentDashboard() {
  const [challenges, setChallenges] = useState<Challenge[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  function load() {
    api<Challenge[]>('/challenges')
      .then((rows) => {
        setChallenges(rows)
        setSelectedId((current) => current ?? rows[0]?.id ?? null)
      })
      .catch((err) => setError(describeError(err)))
  }

  useEffect(load, [])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Department dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Post a problem in plain language, review what the analyzer structured, and decide.
        </p>
      </div>

      <ErrorNote error={error} />
      <NewChallenge onCreated={load} />

      <Section title="Challenges" description="Everything this department has raised.">
        {challenges.length === 0 ? (
          <Empty>No challenges yet. Create one above.</Empty>
        ) : (
          <div className="space-y-2">
            {challenges.map((challenge) => (
              <button
                key={challenge.id}
                type="button"
                onClick={() => setSelectedId(challenge.id)}
                className={`flex w-full flex-wrap items-center gap-2 rounded-md border p-3 text-left text-sm ${
                  selectedId === challenge.id ? 'border-primary bg-accent' : 'border-border'
                }`}
              >
                <span className="font-medium">{challenge.title}</span>
                <Badge variant="outline">{challenge.status}</Badge>
                {challenge.tier && <Badge variant="secondary">{challenge.tier}</Badge>}
                {challenge.missing_fields && challenge.missing_fields.length > 0 && (
                  <Badge variant="warning">{challenge.missing_fields.length} missing</Badge>
                )}
              </button>
            ))}
          </div>
        )}
      </Section>

      {selectedId && <ChallengeDetail challengeId={selectedId} onChanged={load} />}
    </div>
  )
}

function NewChallenge({ onCreated }: { onCreated: () => void }) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState('WATER')
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [prior, setPrior] = useState<PriorPilot[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function analyze() {
    setBusy(true)
    setError(null)
    try {
      setAnalysis(await api<Analysis>('/challenges/analyze', {
        method: 'POST',
        body: JSON.stringify({ description }),
      }))
      const knowledge = await api<{ matches: PriorPilot[] }>('/challenges/knowledge-search', {
        method: 'POST',
        body: JSON.stringify({ description }),
      })
      setPrior(knowledge.matches)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setBusy(false)
    }
  }

  async function create() {
    setBusy(true)
    setError(null)
    try {
      await api('/challenges', {
        method: 'POST',
        body: JSON.stringify({ title, description, department_id: 1, category }),
      })
      setTitle('')
      setDescription('')
      setAnalysis(null)
      setPrior([])
      onCreated()
    } catch (err) {
      setError(describeError(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Section
      title="Post a problem"
      description="Write it the way you would describe it to a colleague. The analyzer does the structuring."
    >
      <div className="space-y-3">
        <Input placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
        <textarea
          className="min-h-28 w-full rounded-md border border-input bg-card p-3 text-sm"
          placeholder="What is going wrong, in plain language?"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        <Input
          placeholder="Category (e.g. WATER)"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        />
        <ErrorNote error={error} />
        <div className="flex gap-2">
          <Button variant="outline" onClick={analyze} disabled={busy || !description.trim()}>
            Analyze
          </Button>
          <Button onClick={create} disabled={busy || !title.trim() || !description.trim()}>
            Create draft
          </Button>
        </div>

        {prior.length > 0 && (
          <div className="rounded-md border border-amber-300 bg-amber-50 p-3">
            <p className="text-sm font-medium text-amber-900">Similar solution piloted before</p>
            {prior.map((match) => (
              <div key={match.challenge_id} className="mt-2 text-xs text-amber-900">
                <p className="font-medium">
                  {match.title} — {match.department} ({(match.similarity * 100).toFixed(0)}% similar)
                </p>
                <p>
                  Outcome {match.outcome}, cost {match.cost}, delivered by {match.startup}.
                </p>
                <p className="italic">{match.lessons_learned}</p>
              </div>
            ))}
          </div>
        )}

        {analysis && <AnalysisPanel analysis={analysis} />}
      </div>
    </Section>
  )
}

function AnalysisPanel({ analysis }: { analysis: Analysis }) {
  return (
    <div className="space-y-3 rounded-md border border-border p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium">Analyzer output</span>
        <Badge variant="outline">source: {analysis.source}</Badge>
        {analysis.source === 'template' && (
          <Badge variant="warning">offline template — no values invented</Badge>
        )}
      </div>
      <Field label="Problem" value={analysis.problem_statement} />
      <div>
        <p className="text-sm text-muted-foreground">Required capabilities</p>
        <ul className="ml-4 list-disc text-sm">
          {analysis.required_capabilities.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>
      <div>
        <p className="text-sm text-muted-foreground">Suggested KPIs</p>
        <ul className="ml-4 list-disc text-sm">
          {analysis.suggested_kpis.map((kpi) => (
            <li key={kpi.name}>
              {kpi.name} — target {kpi.target_value ?? 'set by the officer'} {kpi.unit} (
              {kpi.direction === 'LOWER_IS_BETTER' ? 'lower is better' : 'higher is better'})
            </li>
          ))}
        </ul>
      </div>
      <div>
        <p className="mb-1 text-sm text-muted-foreground">Missing fields</p>
        <MissingFields fields={analysis.missing_fields} />
      </div>
    </div>
  )
}

function ChallengeDetail({
  challengeId,
  onChanged,
}: {
  challengeId: number
  onChanged: () => void
}) {
  const [challenge, setChallenge] = useState<Challenge | null>(null)
  const [proposals, setProposals] = useState<Proposal[]>([])
  const [barriers, setBarriers] = useState<BarrierFlag[] | null>(null)
  const [pilot, setPilot] = useState<Pilot | null>(null)
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null)
  const [kpis, setKpis] = useState<Kpi[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  function load() {
    api<Challenge>(`/challenges/${challengeId}`).then(setChallenge).catch(() => setChallenge(null))
    api<Proposal[]>(`/challenges/${challengeId}/proposals`).then(setProposals).catch(() => {})
    api<Kpi[]>(`/challenges/${challengeId}/kpis`).then(setKpis).catch(() => {})
  }

  useEffect(load, [challengeId])

  async function act(action: () => Promise<unknown>) {
    setBusy(true)
    setError(null)
    try {
      await action()
      load()
      onChanged()
    } catch (err) {
      setError(describeError(err))
    } finally {
      setBusy(false)
    }
  }

  if (!challenge) return null
  const spec = (challenge.structured_spec ?? {}) as Record<string, unknown>

  return (
    <div className="space-y-4">
      <Section
        title={challenge.title}
        description={challenge.description_raw}
        action={<Badge variant="outline">{challenge.status}</Badge>}
      >
        <div className="grid gap-2 sm:grid-cols-2">
          <Field label="Budget" value={challenge.value} />
          <Field label="Timeline" value={(spec.timeline as string) ?? null} />
          <Field label="District" value={challenge.district} />
          <Field label="Criticality" value={challenge.criticality} />
          <Field label="Innovation potential" value={challenge.innovation_potential} />
          <Field label="Requires on-site work" value={challenge.requires_onsite ? 'Yes' : 'No'} />
        </div>
        <div className="mt-3">
          <MissingFields fields={challenge.missing_fields} />
        </div>
        <ErrorNote error={error} />
      </Section>

      {challenge.missing_fields && challenge.missing_fields.length > 0 && (
        <FillGaps challengeId={challenge.id} onSaved={() => act(async () => {})} />
      )}

      {challenge.tier_explanation && (
        <Section title={`Tier: ${challenge.tier}`} description="Why the engine classified it this way.">
          <p className="text-sm">{challenge.tier_explanation}</p>
        </Section>
      )}

      <Section
        title="Barrier analysis"
        description="Eligibility criteria that shut startups out. The engine flags; you decide."
        action={
          <Button
            size="sm"
            variant="outline"
            disabled={busy}
            onClick={() =>
              act(async () => {
                const result = await api<{ criteria: BarrierFlag[] }>('/engine/barrier-analysis', {
                  method: 'POST',
                  body: JSON.stringify({ criteria: BARRIER_CODES }),
                })
                setBarriers(result.criteria)
              })
            }
          >
            Check standard criteria
          </Button>
        }
      >
        {!barriers ? (
          <Empty>Run the check to see which traditional criteria would exclude startups.</Empty>
        ) : (
          <div className="space-y-2">
            {barriers.map((flag) => (
              <div key={flag.code} className="rounded-md border border-border p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium">{flag.label}</span>
                  <Badge variant={flag.excludes_startups ? 'warning' : 'outline'}>
                    {flag.excludes_startups ? 'excludes startups' : flag.classification}
                  </Badge>
                  <Badge variant="outline">{flag.classification}</Badge>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{flag.reason}</p>
                {flag.rule_cited && (
                  <p className="mt-1 text-xs text-muted-foreground">Rule cited: {flag.rule_cited}</p>
                )}
                <p className="mt-1 text-xs font-medium">{flag.officer_action}</p>
              </div>
            ))}
          </div>
        )}
      </Section>

      {!challenge.kpis_locked && (
        <ApproveKpis challengeId={challenge.id} onApproved={() => act(async () => {})} />
      )}

      {challenge.kpis_locked && challenge.status === 'APPROVED' && (
        <Section title="Publish" description="Classifies the tier and opens the bid window.">
          <Button
            disabled={busy}
            onClick={() =>
              act(() => api(`/challenges/${challenge.id}/publish`, { method: 'POST' }))
            }
          >
            Publish challenge
          </Button>
        </Section>
      )}

      <Section title="Applicants" description="Everyone who bid, with their score breakdown.">
        {proposals.length === 0 ? (
          <Empty>No proposals yet.</Empty>
        ) : (
          <div className="space-y-3">
            {proposals.map((proposal) => (
              <ApplicantRow
                key={proposal.id}
                proposal={proposal}
                busy={busy}
                onAward={() =>
                  act(() =>
                    api(`/proposals/${proposal.id}/award`, {
                      method: 'POST',
                      body: JSON.stringify({ note: 'Awarded after evaluation.' }),
                    }),
                  )
                }
                onDecline={(code, detail) =>
                  act(() =>
                    api(`/proposals/${proposal.id}/decline`, {
                      method: 'POST',
                      body: JSON.stringify({
                        decline_reason_code: code,
                        decline_detail: detail,
                      }),
                    }),
                  )
                }
              />
            ))}
          </div>
        )}
      </Section>

      {kpis.length > 0 && (
        <Section title="KPI tracking" description="Claimed by the supplier, validated independently.">
          <div className="space-y-2">
            {kpis.map((kpi) => (
              <div key={kpi.id} className="rounded-md border border-border p-3 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{kpi.name}</span>
                  <Badge variant="outline">{kpi.status}</Badge>
                  <Badge variant="secondary">
                    {kpi.direction === 'LOWER_IS_BETTER' ? 'lower is better' : 'higher is better'}
                  </Badge>
                  {kpi.startup_id === null && <Badge variant="outline">specification</Badge>}
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  target {kpi.target_value} {kpi.unit} · claimed {kpi.claimed_value ?? '—'} ·
                  validated {kpi.validated_value ?? '—'}
                </p>
              </div>
            ))}
          </div>
        </Section>
      )}

      <PilotPanel
        challengeId={challenge.id}
        pilot={pilot}
        setPilot={setPilot}
        recommendation={recommendation}
        setRecommendation={setRecommendation}
        busy={busy}
        act={act}
      />
    </div>
  )
}

function FillGaps({ challengeId, onSaved }: { challengeId: number; onSaved: () => void }) {
  const [budget, setBudget] = useState('')
  const [timeline, setTimeline] = useState('')
  const [district, setDistrict] = useState('')
  const [criticality, setCriticality] = useState('MEDIUM')
  const [innovation, setInnovation] = useState('HIGH')
  const [error, setError] = useState<string | null>(null)

  async function save() {
    setError(null)
    try {
      await api(`/challenges/${challengeId}`, {
        method: 'PATCH',
        body: JSON.stringify({
          budget: budget || undefined,
          timeline: timeline || undefined,
          district: district || undefined,
          criticality,
          innovation_potential: innovation,
        }),
      })
      onSaved()
    } catch (err) {
      setError(describeError(err))
    }
  }

  return (
    <Section
      title="Fill in what the department owns"
      description="The analyzer never supplies these. Publishing is blocked until they are here."
    >
      <div className="grid gap-2 sm:grid-cols-2">
        <Input placeholder="Budget in rupees" value={budget} onChange={(e) => setBudget(e.target.value)} />
        <Input placeholder="Timeline, e.g. 6 months" value={timeline} onChange={(e) => setTimeline(e.target.value)} />
        <Input placeholder="District" value={district} onChange={(e) => setDistrict(e.target.value)} />
        <select
          className="h-10 rounded-md border border-input bg-card px-3 text-sm"
          value={criticality}
          onChange={(e) => setCriticality(e.target.value)}
        >
          {['LOW', 'MEDIUM', 'HIGH'].map((level) => (
            <option key={level} value={level}>
              criticality: {level}
            </option>
          ))}
        </select>
        <select
          className="h-10 rounded-md border border-input bg-card px-3 text-sm"
          value={innovation}
          onChange={(e) => setInnovation(e.target.value)}
        >
          {['LOW', 'MEDIUM', 'HIGH'].map((level) => (
            <option key={level} value={level}>
              innovation: {level}
            </option>
          ))}
        </select>
      </div>
      <ErrorNote error={error} />
      <Button className="mt-3" onClick={save}>
        Save
      </Button>
    </Section>
  )
}

function ApproveKpis({
  challengeId,
  onApproved,
}: {
  challengeId: number
  onApproved: () => void
}) {
  const [rows, setRows] = useState([
    {
      name: 'Leak localisation accuracy',
      target_value: '85',
      unit: 'percent',
      measurement_method: 'Field verification against excavation results',
      direction: 'HIGHER_IS_BETTER',
    },
    {
      name: 'Time to locate a reported burst',
      target_value: '12',
      unit: 'hours',
      measurement_method: 'Report timestamp to field confirmation',
      direction: 'LOWER_IS_BETTER',
    },
  ])
  const [error, setError] = useState<string | null>(null)

  function update(index: number, key: string, value: string) {
    setRows((current) =>
      current.map((row, position) => (position === index ? { ...row, [key]: value } : row)),
    )
  }

  async function approve() {
    setError(null)
    try {
      await api(`/challenges/${challengeId}/approve`, {
        method: 'POST',
        body: JSON.stringify({ kpis: rows, note: 'KPIs agreed with the executive engineer.' }),
      })
      onApproved()
    } catch (err) {
      setError(describeError(err))
    }
  }

  return (
    <Section
      title="Approve and lock KPIs"
      description="Approval fixes what the pilot will be judged against. After this they cannot be changed."
    >
      <div className="space-y-2">
        {rows.map((row, index) => (
          <div key={index} className="grid gap-2 rounded-md border border-border p-3 sm:grid-cols-4">
            <Input value={row.name} onChange={(e) => update(index, 'name', e.target.value)} />
            <Input
              value={row.target_value}
              onChange={(e) => update(index, 'target_value', e.target.value)}
              placeholder="target"
            />
            <Input value={row.unit} onChange={(e) => update(index, 'unit', e.target.value)} />
            <select
              className="h-10 rounded-md border border-input bg-card px-2 text-sm"
              value={row.direction}
              onChange={(e) => update(index, 'direction', e.target.value)}
            >
              <option value="HIGHER_IS_BETTER">higher is better</option>
              <option value="LOWER_IS_BETTER">lower is better</option>
            </select>
          </div>
        ))}
      </div>
      <ErrorNote error={error} />
      <Button className="mt-3" onClick={approve}>
        Approve and lock
      </Button>
    </Section>
  )
}

function ApplicantRow({
  proposal,
  busy,
  onAward,
  onDecline,
}: {
  proposal: Proposal
  busy: boolean
  onAward: () => void
  onDecline: (code: string, detail: string) => void
}) {
  const [code, setCode] = useState(DECLINE_CODES[0])
  const [detail, setDetail] = useState('')
  const [open, setOpen] = useState(false)

  return (
    <div className="rounded-md border border-border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium">Proposal #{proposal.id}</span>
        <Badge variant="outline">{proposal.status}</Badge>
        {proposal.total_score && <Badge variant="secondary">score {proposal.total_score}</Badge>}
        {proposal.decline_reason_code && (
          <Badge variant="warning">{proposal.decline_reason_code}</Badge>
        )}
      </div>
      <p className="mt-1 text-sm">{proposal.summary}</p>
      {proposal.sub_scores?.explanation && (
        <p className="mt-1 text-xs text-muted-foreground">{proposal.sub_scores.explanation}</p>
      )}

      {proposal.status !== 'AWARDED' && proposal.status !== 'DECLINED' && (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button size="sm" disabled={busy} onClick={onAward}>
            Award
          </Button>
          <Button size="sm" variant="outline" onClick={() => setOpen((value) => !value)}>
            Decline
          </Button>
        </div>
      )}

      {open && (
        <div className="mt-2 space-y-2 rounded-md border border-dashed border-border p-3">
          <select
            className="h-10 w-full rounded-md border border-input bg-card px-2 text-sm"
            value={code}
            onChange={(e) => setCode(e.target.value)}
          >
            {DECLINE_CODES.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
          <Input
            placeholder="What the startup is told (required)"
            value={detail}
            onChange={(e) => setDetail(e.target.value)}
          />
          <p className="text-xs text-muted-foreground">
            A decline always carries a coded reason. The startup sees this and its own sub-score
            breakdown.
          </p>
          <Button size="sm" disabled={!detail.trim()} onClick={() => onDecline(code, detail)}>
            Confirm decline
          </Button>
        </div>
      )}
    </div>
  )
}

function PilotPanel({
  challengeId,
  pilot,
  setPilot,
  recommendation,
  setRecommendation,
  busy,
  act,
}: {
  challengeId: number
  pilot: Pilot | null
  setPilot: (value: Pilot | null) => void
  recommendation: Recommendation | null
  setRecommendation: (value: Recommendation | null) => void
  busy: boolean
  act: (action: () => Promise<unknown>) => Promise<void>
}) {
  const [draft, setDraft] = useState<{ milestones: Record<string, unknown>[] } | null>(null)

  return (
    <Section title="Pilot" description="Milestones are drafted from the locked KPIs; you approve them.">
      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          variant="outline"
          disabled={busy}
          onClick={() =>
            act(async () => {
              setDraft(
                await api<{ milestones: Record<string, unknown>[] }>(
                  `/challenges/${challengeId}/milestone-draft`,
                ),
              )
            })
          }
        >
          Draft milestones
        </Button>
        {draft && (
          <Button
            size="sm"
            disabled={busy}
            onClick={() =>
              act(async () => {
                const created = await api<Pilot>(`/challenges/${challengeId}/pilot`, {
                  method: 'POST',
                  body: JSON.stringify({
                    milestones: draft.milestones,
                    started_on: new Date().toISOString().slice(0, 10),
                    planned_end_on: new Date(Date.now() + 120 * 86400000)
                      .toISOString()
                      .slice(0, 10),
                    note: 'Plan approved by the officer.',
                  }),
                })
                setPilot(created)
              })
            }
          >
            Approve plan and start pilot
          </Button>
        )}
        {pilot && (
          <Button
            size="sm"
            variant="outline"
            disabled={busy}
            onClick={() =>
              act(async () => {
                setRecommendation(
                  await api<Recommendation>(`/pilots/${pilot.id}/recommendation`),
                )
              })
            }
          >
            Compute recommendation
          </Button>
        )}
      </div>

      {draft && (
        <ul className="mt-3 ml-4 list-disc text-sm">
          {draft.milestones.map((milestone, index) => (
            <li key={index}>
              {String(milestone.name)} — {String(milestone.purpose)}
            </li>
          ))}
        </ul>
      )}

      {recommendation && pilot && (
        <div className="mt-3 rounded-md border border-border p-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium">
              Recommendation: {recommendation.recommended_outcome}
            </span>
            <Badge variant="warning">not in effect until you decide</Badge>
          </div>
          <ul className="mt-2 ml-4 list-disc text-xs text-muted-foreground">
            {recommendation.reasoning.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
          <div className="mt-3 flex flex-wrap gap-2">
            {['SCALE', 'MODIFY', 'REJECT'].map((outcome) => (
              <Button
                key={outcome}
                size="sm"
                variant={outcome === recommendation.recommended_outcome ? 'default' : 'outline'}
                disabled={busy}
                onClick={() =>
                  act(() =>
                    api(`/pilots/${pilot.id}/decision`, {
                      method: 'POST',
                      body: JSON.stringify({
                        outcome,
                        note: `Officer decision recorded: ${outcome}.`,
                        completed_on: new Date().toISOString().slice(0, 10),
                      }),
                    }),
                  )
                }
              >
                Decide {outcome}
              </Button>
            ))}
          </div>
        </div>
      )}
    </Section>
  )
}
