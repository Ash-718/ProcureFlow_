import { useEffect, useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  describeError,
  Empty,
  ErrorNote,
  Section,
  SubScoreTable,
} from '@/components/common'
import { api } from '@/lib/api'
import type { Match, Proposal } from '@/types'

interface Brief {
  proposal_id: number
  challenge_title: string
  company_name: string
  ai_summary: { source: string; summary: string; note: string }
  computed_match: Match | null
  rubric: string[]
  note: string
}

export function ExpertEvaluation() {
  const [queue, setQueue] = useState<Proposal[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  function load() {
    api<Proposal[]>('/evaluations/queue')
      .then(setQueue)
      .catch((err) => setError(describeError(err)))
  }

  useEffect(load, [])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Evaluation queue</h1>
        <p className="text-sm text-muted-foreground">
          Claim a proposal, read the AI-assisted summary, and score the rubric yourself. Your
          marks are recorded separately from anything the platform computed.
        </p>
      </div>

      <ErrorNote error={error} />

      <Section title="Queue" description="Unclaimed proposals, and the ones you hold.">
        {queue.length === 0 ? (
          <Empty>Nothing waiting for evaluation.</Empty>
        ) : (
          <div className="space-y-2">
            {queue.map((proposal) => (
              <div
                key={proposal.id}
                className="flex flex-wrap items-center gap-2 rounded-md border border-border p-3 text-sm"
              >
                <span className="font-medium">Proposal #{proposal.id}</span>
                <Badge variant="outline">{proposal.status}</Badge>
                {proposal.total_score && (
                  <Badge variant="secondary">computed {proposal.total_score}</Badge>
                )}
                {proposal.claimed_by_user_id && <Badge variant="outline">claimed</Badge>}
                <div className="ml-auto flex gap-2">
                  {!proposal.claimed_by_user_id && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={async () => {
                        try {
                          await api(`/proposals/${proposal.id}/claim`, { method: 'POST' })
                          load()
                        } catch (err) {
                          setError(describeError(err))
                        }
                      }}
                    >
                      Claim
                    </Button>
                  )}
                  <Button size="sm" onClick={() => setSelected(proposal.id)}>
                    Open
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>

      {selected && <EvaluationPanel proposalId={selected} onScored={load} />}
    </div>
  )
}

function EvaluationPanel({
  proposalId,
  onScored,
}: {
  proposalId: number
  onScored: () => void
}) {
  const [brief, setBrief] = useState<Brief | null>(null)
  const [marks, setMarks] = useState<Record<string, { score: string; reason: string }>>({})
  const [note, setNote] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    setSaved(false)
    api<Brief>(`/proposals/${proposalId}/evaluation-brief`)
      .then((data) => {
        setBrief(data)
        setMarks(
          Object.fromEntries(data.rubric.map((item) => [item, { score: '', reason: '' }])),
        )
      })
      .catch((err) => setError(describeError(err)))
  }, [proposalId])

  async function submit() {
    setError(null)
    try {
      await api(`/proposals/${proposalId}/evaluation`, {
        method: 'POST',
        body: JSON.stringify({
          scores: Object.entries(marks)
            .filter(([, mark]) => mark.score !== '')
            .map(([criterion, mark]) => ({
              criterion,
              score: Number(mark.score),
              reason: mark.reason || 'No comment recorded.',
            })),
          note,
        }),
      })
      setSaved(true)
      onScored()
    } catch (err) {
      setError(describeError(err))
    }
  }

  if (!brief) return null

  return (
    <div className="space-y-4">
      <Section
        title={brief.challenge_title}
        description={`Bid from ${brief.company_name}`}
        action={<Badge variant="outline">AI summary: {brief.ai_summary.source}</Badge>}
      >
        <p className="text-sm">{brief.ai_summary.summary}</p>
        <p className="mt-2 text-xs text-muted-foreground">{brief.ai_summary.note}</p>
      </Section>

      {brief.computed_match && (
        <Section
          title="Computed match"
          description="Prototype-generated, for context. It is not your score."
        >
          <SubScoreTable
            subScores={brief.computed_match.sub_scores}
            proximity={brief.computed_match.proximity}
          />
        </Section>
      )}

      <Section title="Your scoring rubric" description="Every mark carries a reason.">
        <div className="space-y-2">
          {brief.rubric.map((criterion) => (
            <div key={criterion} className="grid gap-2 rounded-md border border-border p-3 sm:grid-cols-3">
              <span className="self-center text-sm font-medium">
                {criterion.replace(/_/g, ' ')}
              </span>
              <Input
                placeholder="0-100"
                value={marks[criterion]?.score ?? ''}
                onChange={(e) =>
                  setMarks((current) => ({
                    ...current,
                    [criterion]: { ...current[criterion], score: e.target.value },
                  }))
                }
              />
              <Input
                placeholder="Reason"
                value={marks[criterion]?.reason ?? ''}
                onChange={(e) =>
                  setMarks((current) => ({
                    ...current,
                    [criterion]: { ...current[criterion], reason: e.target.value },
                  }))
                }
              />
            </div>
          ))}
        </div>
        <Input
          className="mt-2"
          placeholder="Overall note (required)"
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
        <ErrorNote error={error} />
        {saved && <p className="mt-2 text-sm">Evaluation recorded.</p>}
        <Button className="mt-3" disabled={!note.trim()} onClick={submit}>
          Submit evaluation
        </Button>
      </Section>
    </div>
  )
}
