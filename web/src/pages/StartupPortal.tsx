import { useEffect, useState } from 'react'

import { useAuth } from '@/auth/AuthContext'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  describeError,
  Empty,
  ErrorNote,
  Field,
  Section,
  SubScoreTable,
} from '@/components/common'
import { api } from '@/lib/api'
import type { Challenge, Kpi, PartnershipView, Proposal } from '@/types'

export function StartupPortal() {
  const { user } = useAuth()
  const [challenges, setChallenges] = useState<Challenge[]>([])
  const [proposals, setProposals] = useState<Proposal[]>([])
  const [error, setError] = useState<string | null>(null)

  function load() {
    api<Challenge[]>('/challenges').then(setChallenges).catch((err) => setError(describeError(err)))
    api<Proposal[]>('/my/proposals').then(setProposals).catch(() => {})
  }

  useEffect(load, [])

  const appliedTo = new Set(proposals.map((proposal) => proposal.challenge_id))
  const openNow = challenges.filter(
    (challenge) => challenge.status === 'PUBLISHED' || challenge.status === 'EVALUATION',
  )
  const closed = challenges.filter(
    (challenge) => challenge.status !== 'PUBLISHED' && challenge.status !== 'EVALUATION',
  )

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">{user?.company?.name}</h1>
        <p className="text-sm text-muted-foreground">
          Sample startup profile for the prototype. Browse open challenges, apply, and report KPI
          evidence from your pilots.
        </p>
      </div>

      <Section title="Profile" description="What the matching engine reads about you.">
        <div className="grid gap-2 sm:grid-cols-2">
          <Field label="Company" value={user?.company?.name} />
          <Field label="District" value={user?.company?.district} />
          <Field label="Type" value={user?.company?.type} />
          <Field label="Sample data" value={<Badge variant="warning">seeded for the demo</Badge>} />
        </div>
      </Section>

      <ErrorNote error={error} />

      <Section title="Open for proposals" description="Work you can bid on right now.">
        {openNow.length === 0 ? (
          <Empty>
            Nothing is open for proposals at the moment. Completed work is listed below.
          </Empty>
        ) : (
          <div className="space-y-2">
            {openNow.map((challenge) => (
              <ChallengeRow
                key={challenge.id}
                challenge={challenge}
                alreadyApplied={appliedTo.has(challenge.id)}
                onApplied={load}
              />
            ))}
          </div>
        )}
      </Section>

      <Section
        title="Closed and completed"
        description="Past work, for reference. The bid window on these has shut."
      >
        {closed.length === 0 ? (
          <Empty>Nothing yet.</Empty>
        ) : (
          <div className="space-y-2">
            {closed.map((challenge) => (
              <ChallengeRow
                key={challenge.id}
                challenge={challenge}
                alreadyApplied={appliedTo.has(challenge.id)}
                onApplied={load}
              />
            ))}
          </div>
        )}
      </Section>

      <Section
        title="My proposals"
        description="Your score breakdown, and the reason for any decline."
      >
        {proposals.length === 0 ? (
          <Empty>You have not bid on anything yet.</Empty>
        ) : (
          <div className="space-y-3">
            {proposals.map((proposal) => (
              <ProposalCard key={proposal.id} proposal={proposal} />
            ))}
          </div>
        )}
      </Section>

      <KpiEvidence />
      <MilestoneStatus />
    </div>
  )
}

function ChallengeRow({
  challenge,
  alreadyApplied,
  onApplied,
}: {
  challenge: Challenge
  alreadyApplied: boolean
  onApplied: () => void
}) {
  const [summary, setSummary] = useState('')
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function apply() {
    setBusy(true)
    setError(null)
    try {
      await api(`/challenges/${challenge.id}/proposals`, {
        method: 'POST',
        body: JSON.stringify({ summary }),
      })
      setOpen(false)
      onApplied()
    } catch (err) {
      setError(describeError(err))
    } finally {
      setBusy(false)
    }
  }

  const open_for_bids = challenge.status === 'PUBLISHED' || challenge.status === 'EVALUATION'

  return (
    <div className="rounded-md border border-border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium">{challenge.title}</span>
        <Badge variant="outline">{challenge.status}</Badge>
        {challenge.tier && <Badge variant="secondary">{challenge.tier}</Badge>}
        {challenge.district && <Badge variant="outline">{challenge.district}</Badge>}
      </div>
      <p className="mt-1 text-xs text-muted-foreground">{challenge.description_raw}</p>
      {challenge.tier_explanation && (
        <p className="mt-1 text-xs text-muted-foreground">{challenge.tier_explanation}</p>
      )}

      {alreadyApplied ? (
        <Badge className="mt-2" variant="outline">
          Applied
        </Badge>
      ) : (
        open_for_bids && (
          <div className="mt-2">
            <Button size="sm" variant="outline" onClick={() => setOpen((value) => !value)}>
              Apply
            </Button>
            {open && (
              <div className="mt-2 space-y-2">
                <Input
                  placeholder="How would you solve it?"
                  value={summary}
                  onChange={(e) => setSummary(e.target.value)}
                />
                <ErrorNote error={error} />
                <Button size="sm" disabled={busy || !summary.trim()} onClick={apply}>
                  Submit proposal
                </Button>
              </div>
            )}
          </div>
        )
      )}
    </div>
  )
}

function ProposalCard({ proposal }: { proposal: Proposal }) {
  return (
    <div className="rounded-md border border-border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium">Challenge #{proposal.challenge_id}</span>
        <Badge variant="outline">{proposal.status}</Badge>
        {proposal.total_score && <Badge variant="secondary">score {proposal.total_score}</Badge>}
      </div>

      {proposal.decline_reason_code && (
        <div className="mt-2 rounded-md border border-amber-300 bg-amber-50 p-3">
          <p className="text-sm font-medium text-amber-900">
            Declined: {proposal.decline_reason_code}
          </p>
          <p className="text-xs text-amber-900">{proposal.decline_detail}</p>
        </div>
      )}

      {proposal.sub_scores?.criteria && (
        <div className="mt-3">
          <p className="mb-2 text-sm text-muted-foreground">Your score breakdown</p>
          <SubScoreTable
            subScores={proposal.sub_scores.criteria}
            proximity={proposal.sub_scores.proximity}
          />
        </div>
      )}
    </div>
  )
}

function KpiEvidence() {
  const [kpis, setKpis] = useState<Kpi[]>([])
  const [challengeId, setChallengeId] = useState('')
  const [error, setError] = useState<string | null>(null)

  async function load() {
    setError(null)
    try {
      setKpis(await api<Kpi[]>(`/challenges/${challengeId}/kpis`))
    } catch (err) {
      setError(describeError(err))
    }
  }

  return (
    <Section
      title="KPI evidence"
      description="Report what you achieved. Someone independent validates it — never you."
    >
      <div className="flex gap-2">
        <Input
          placeholder="Challenge id"
          value={challengeId}
          onChange={(e) => setChallengeId(e.target.value)}
        />
        <Button variant="outline" onClick={load} disabled={!challengeId}>
          Load KPIs
        </Button>
      </div>
      <ErrorNote error={error} />
      <div className="mt-3 space-y-2">
        {kpis
          .filter((kpi) => kpi.startup_id !== null)
          .map((kpi) => (
            <KpiRow key={kpi.id} kpi={kpi} onSubmitted={load} />
          ))}
        {kpis.length === 0 && <Empty>Load a challenge to see its KPIs.</Empty>}
      </div>
    </Section>
  )
}

function KpiRow({ kpi, onSubmitted }: { kpi: Kpi; onSubmitted: () => void }) {
  const [value, setValue] = useState('')
  const [evidence, setEvidence] = useState('')
  const [error, setError] = useState<string | null>(null)

  async function submit() {
    setError(null)
    try {
      await api(`/kpis/${kpi.id}/evidence`, {
        method: 'POST',
        body: JSON.stringify({ claimed_value: value, evidence }),
      })
      onSubmitted()
    } catch (err) {
      setError(describeError(err))
    }
  }

  return (
    <div className="rounded-md border border-border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium">{kpi.name}</span>
        <Badge variant="outline">{kpi.status}</Badge>
        <Badge variant="secondary">
          target {kpi.target_value} {kpi.unit}
        </Badge>
        <Badge variant="outline">
          {kpi.direction === 'LOWER_IS_BETTER' ? 'lower is better' : 'higher is better'}
        </Badge>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        claimed {kpi.claimed_value ?? '—'} · validated {kpi.validated_value ?? '—'}
      </p>
      {kpi.status !== 'VERIFIED' && (
        <div className="mt-2 grid gap-2 sm:grid-cols-3">
          <Input placeholder="Achieved value" value={value} onChange={(e) => setValue(e.target.value)} />
          <Input
            placeholder="Evidence"
            value={evidence}
            onChange={(e) => setEvidence(e.target.value)}
          />
          <Button size="sm" disabled={!value || !evidence} onClick={submit}>
            Submit evidence
          </Button>
        </div>
      )}
      <ErrorNote error={error} />
    </div>
  )
}

function MilestoneStatus() {
  const [partnershipId, setPartnershipId] = useState('')
  const [view, setView] = useState<PartnershipView | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function load() {
    setError(null)
    try {
      setView(await api<PartnershipView>(`/partnerships/${partnershipId}`))
    } catch (err) {
      setError(describeError(err))
    }
  }

  return (
    <Section
      title="Milestone and payment status"
      description="Display only. This prototype has no payment integration."
    >
      <div className="flex gap-2">
        <Input
          placeholder="Partnership id"
          value={partnershipId}
          onChange={(e) => setPartnershipId(e.target.value)}
        />
        <Button variant="outline" onClick={load} disabled={!partnershipId}>
          Load
        </Button>
      </div>
      <ErrorNote error={error} />
      {view && (
        <div className="mt-3 space-y-2">
          <p className="text-xs text-muted-foreground">{view.payment_note}</p>
          {(view.partnership.milestone_status ?? []).map((milestone) => (
            <div
              key={milestone.milestone}
              className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border p-2 text-sm"
            >
              <span>{milestone.milestone}</span>
              <span className="flex gap-2">
                <Badge variant="outline">{milestone.status}</Badge>
                <Badge variant="secondary">pays {milestone.payment_to}</Badge>
              </span>
            </div>
          ))}
        </div>
      )}
    </Section>
  )
}
