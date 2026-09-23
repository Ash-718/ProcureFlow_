import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { api } from '@/lib/api'

interface ProcurementRule {
  id: number
  rule_name: string
  rule_type: string
  value: string
  active: boolean
  source_reference: string | null
  effective_from: string
  description: string | null
}

function RuleRow({ rule, onSaved }: { rule: ProcurementRule; onSaved: () => void }) {
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState(rule.value)
  const [effectiveFrom, setEffectiveFrom] = useState(rule.effective_from)
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function save() {
    setBusy(true)
    setError(null)
    try {
      await api(`/admin/rules/${rule.id}`, {
        method: 'PUT',
        body: JSON.stringify({ value, effective_from: effectiveFrom, reason }),
      })
      setEditing(false)
      setReason('')
      onSaved()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save the rule')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex flex-wrap items-center gap-2 text-base">
          <span className="font-mono">{rule.rule_name}</span>
          <Badge variant="secondary">{rule.value}</Badge>
          <Badge variant="outline">{rule.rule_type}</Badge>
          {rule.source_reference ? (
            <Badge variant="outline">sourced</Badge>
          ) : (
            <Badge variant="warning">prototype setting — no source reference</Badge>
          )}
          {!rule.active && <Badge variant="outline">inactive</Badge>}
        </CardTitle>
        <CardDescription>{rule.description}</CardDescription>
      </CardHeader>

      <CardContent className="space-y-3 text-sm">
        <p>
          <span className="text-muted-foreground">Effective from </span>
          {rule.effective_from}
        </p>
        <p>
          <span className="text-muted-foreground">Source reference </span>
          {rule.source_reference ?? (
            <span className="text-amber-700">
              none — this value is a working assumption, not a verified legal requirement
            </span>
          )}
        </p>

        {editing ? (
          <div className="space-y-2 rounded-md border border-border p-3">
            <div className="grid gap-2 sm:grid-cols-2">
              <label className="space-y-1">
                <span className="text-xs text-muted-foreground">Value</span>
                <Input value={value} onChange={(e) => setValue(e.target.value)} />
              </label>
              <label className="space-y-1">
                <span className="text-xs text-muted-foreground">Effective from</span>
                <Input
                  type="date"
                  value={effectiveFrom}
                  onChange={(e) => setEffectiveFrom(e.target.value)}
                />
              </label>
            </div>
            <label className="block space-y-1">
              <span className="text-xs text-muted-foreground">
                Reason for the change (recorded in the audit log, required)
              </span>
              <Input value={reason} onChange={(e) => setReason(e.target.value)} />
            </label>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <div className="flex gap-2">
              <Button size="sm" onClick={save} disabled={busy || !reason.trim()}>
                {busy ? 'Saving…' : 'Save'}
              </Button>
              <Button size="sm" variant="outline" onClick={() => setEditing(false)}>
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
            Edit
          </Button>
        )}
      </CardContent>
    </Card>
  )
}

export function AdminRulesPage() {
  const [rules, setRules] = useState<ProcurementRule[]>([])
  const [error, setError] = useState<string | null>(null)

  function load() {
    api<ProcurementRule[]>('/admin/rules')
      .then(setRules)
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load rules'))
  }

  useEffect(load, [])

  return (
    <div className="mx-auto max-w-4xl space-y-4 p-8">
      <Link className="text-sm text-muted-foreground hover:underline" to="/">
        ← Back
      </Link>
      <div>
        <h1 className="text-2xl font-semibold">Procurement rules</h1>
        <p className="text-sm text-muted-foreground">
          Every threshold the tier engine and the eligibility gates apply is read from this
          table. Changing a value here changes how the platform behaves, and the change is
          recorded in the audit log with your reason.
        </p>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="space-y-3">
        {rules.map((rule) => (
          <RuleRow key={rule.id} rule={rule} onSaved={load} />
        ))}
      </div>
    </div>
  )
}
