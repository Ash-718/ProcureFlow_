import { useEffect, useState } from 'react'
import {
  Bar,
  BarChart,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { Badge } from '@/components/ui/badge'
import { describeError, Empty, ErrorNote, Section } from '@/components/common'
import { api } from '@/lib/api'
import type { AuditEntry, Fairness } from '@/types'

/**
 * Palette: slots 1-3 of the validated categorical set, which clears all-pairs
 * CVD and normal-vision separation in both modes. Light-mode aqua sits below
 * 3:1 on the surface, so every bar carries a visible direct label.
 */
const TIER_COLOR: Record<string, string> = {
  SMALL: 'var(--series-1)',
  MEDIUM: 'var(--series-2)',
  LARGE: 'var(--series-3)',
}

/** Indian digit grouping, so a crore does not read as a stray run of zeros. */
function formatRupees(value: string): string {
  const amount = Number(value)
  if (!Number.isFinite(amount)) return value
  return amount.toLocaleString('en-IN', { maximumFractionDigits: 0 })
}

export function FairnessDashboard() {
  const [data, setData] = useState<Fairness | null>(null)
  const [audit, setAudit] = useState<AuditEntry[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api<Fairness>('/admin/fairness').then(setData).catch((err) => setError(describeError(err)))
    api<AuditEntry[]>('/admin/audit-log?limit=60').then(setAudit).catch(() => {})
  }, [])

  return (
    <div className="viz-root space-y-6">
      <style>{`
        .viz-root {
          --surface-1: #fcfcfb;
          --series-1: #2a78d6;
          --series-2: #eb6834;
          --series-3: #1baf7a;
          --grid: #e6e5e1;
        }
        @media (prefers-color-scheme: dark) {
          :root:where(:not([data-theme="light"])) .viz-root {
            --surface-1: #1a1a19;
            --series-1: #3987e5;
            --series-2: #d95926;
            --series-3: #199e70;
            --grid: #34332f;
          }
        }
        :root[data-theme="dark"] .viz-root {
          --surface-1: #1a1a19;
          --series-1: #3987e5;
          --series-2: #d95926;
          --series-3: #199e70;
          --grid: #34332f;
        }
      `}</style>

      <div>
        <h1 className="text-2xl font-semibold">Fairness and governance</h1>
        <p className="text-sm text-muted-foreground">
          Counted per founder group, not per company: the same people behind several entities
          read as one supplier here. All figures are from sample data.
        </p>
      </div>

      <ErrorNote error={error} />
      {!data ? (
        <Empty>Loading.</Empty>
      ) : (
        <>
          <Participation data={data.startup_participation} />
          <TierDistribution rows={data.tier_distribution} />
          <FounderGroups rows={data.founder_groups} />
          <ExecutionFirms rows={data.execution_firms} />
        </>
      )}

      <AuditTrail entries={audit} />
    </div>
  )
}

function Participation({ data }: { data: Fairness['startup_participation'] }) {
  const target = data.target_pct ?? 0
  const share = data.share_pct

  return (
    <Section
      title="Startup participation"
      description="Share of awards going to startups, against the platform's target."
    >
      <div className="flex flex-wrap items-end gap-6">
        <div>
          <p className="text-4xl font-semibold tabular-nums">{share.toFixed(1)}%</p>
          <p className="text-sm text-muted-foreground">
            {data.startup_awards} of {data.total_awards} awards
          </p>
        </div>
        <div>
          <p className="text-2xl font-semibold tabular-nums text-muted-foreground">
            {data.target_pct === null ? '—' : `${target}%`}
          </p>
          <p className="text-sm text-muted-foreground">target</p>
        </div>
      </div>

      {/* One measure against one target: a single track with a target marker. */}
      <div className="relative mt-4 h-4 w-full rounded-md bg-[var(--grid)]">
        <div
          className="h-4 rounded-md"
          style={{
            width: `${Math.min(share, 100)}%`,
            backgroundColor: 'var(--series-1)',
          }}
        />
        {data.target_pct !== null && (
          <div
            className="absolute top-[-4px] h-6 w-0.5 bg-foreground"
            style={{ left: `${Math.min(target, 100)}%` }}
            title={`target ${target}%`}
          />
        )}
      </div>

      <div className="mt-3 rounded-md border border-amber-300 bg-amber-50 p-3">
        <p className="text-xs text-amber-900">
          {data.target_is_prototype_setting && (
            <Badge variant="warning" className="mr-2">
              no source reference
            </Badge>
          )}
          {data.target_label}
        </p>
      </div>
    </Section>
  )
}

function TierDistribution({ rows }: { rows: Fairness['tier_distribution'] }) {
  const order = ['SMALL', 'MEDIUM', 'LARGE']
  const data = order
    .map((tier) => rows.find((row) => row.tier === tier) ?? { tier, challenges: 0 })
    .filter((row) => rows.some((r) => r.tier === row.tier) || row.challenges > 0)

  return (
    <Section title="Tier distribution" description="Where challenges are landing.">
      {data.length === 0 ? (
        <Empty>No classified challenges yet.</Empty>
      ) : (
        <>
          <div className="h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data} margin={{ top: 20, right: 8, bottom: 4, left: 8 }}>
                <XAxis
                  dataKey="tier"
                  tickLine={false}
                  axisLine={{ stroke: 'var(--grid)' }}
                  tick={{ fontSize: 12, fill: 'currentColor' }}
                />
                <YAxis
                  allowDecimals={false}
                  tickLine={false}
                  axisLine={false}
                  width={28}
                  tick={{ fontSize: 12, fill: 'currentColor' }}
                />
                <Tooltip
                  cursor={{ fill: 'var(--grid)', fillOpacity: 0.4 }}
                  contentStyle={{
                    borderRadius: 8,
                    border: '1px solid var(--grid)',
                    fontSize: 12,
                  }}
                />
                <Bar dataKey="challenges" radius={[4, 4, 0, 0]} maxBarSize={72}>
                  {data.map((row) => (
                    <Cell
                      key={row.tier}
                      fill={TIER_COLOR[row.tier]}
                      stroke="var(--surface-1)"
                      strokeWidth={2}
                    />
                  ))}
                  {/* Direct labels: identity and value never rest on colour alone. */}
                  <LabelList
                    dataKey="challenges"
                    position="top"
                    style={{ fontSize: 12, fill: 'currentColor' }}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <table className="mt-2 w-full text-sm">
            <tbody>
              {data.map((row) => (
                <tr key={row.tier} className="border-t border-border">
                  <td className="py-1">{row.tier}</td>
                  <td className="py-1 text-right tabular-nums">{row.challenges}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </Section>
  )
}

function FounderGroups({ rows }: { rows: Fairness['founder_groups'] }) {
  return (
    <Section
      title="Opportunities per founder group"
      description="Awards resolved to the people behind the companies."
    >
      {rows.length === 0 ? (
        <Empty>No awards recorded yet.</Empty>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground">
                <th className="py-2 font-medium">Founder group</th>
                <th className="py-2 font-medium">Companies</th>
                <th className="px-4 py-2 text-right font-medium">Awards</th>
                <th className="py-2 text-right font-medium">Value</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.founders.join('|')} className="border-b border-border align-top">
                  <td className="py-2">
                    {row.founders.join(', ')}
                    {row.company_count > 1 && (
                      <Badge className="ml-2" variant="warning">
                        {row.company_count} entities
                      </Badge>
                    )}
                    {row.note && (
                      <p className="mt-1 text-xs text-muted-foreground">{row.note}</p>
                    )}
                  </td>
                  <td className="py-2 text-muted-foreground">{row.companies.join(', ')}</td>
                  <td className="px-4 py-2 text-right tabular-nums">{row.awards}</td>
                  <td className="whitespace-nowrap py-2 text-right tabular-nums">
                    {formatRupees(row.total_value)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  )
}

function ExecutionFirms({ rows }: { rows: Fairness['execution_firms'] }) {
  return (
    <Section
      title="Partnerships per execution firm"
      description="Concentration on the prime-contractor side of LARGE-tier work."
    >
      {rows.length === 0 ? (
        <Empty>No partnerships recorded yet.</Empty>
      ) : (
        <div className="h-56 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={rows}
              layout="vertical"
              margin={{ top: 4, right: 32, bottom: 4, left: 8 }}
            >
              <XAxis type="number" hide allowDecimals={false} />
              <YAxis
                type="category"
                dataKey="firm"
                width={180}
                tickLine={false}
                axisLine={false}
                tick={{ fontSize: 12, fill: 'currentColor' }}
              />
              <Tooltip
                cursor={{ fill: 'var(--grid)', fillOpacity: 0.4 }}
                contentStyle={{ borderRadius: 8, border: '1px solid var(--grid)', fontSize: 12 }}
              />
              <Bar
                dataKey="partnerships"
                fill="var(--series-1)"
                radius={[0, 4, 4, 0]}
                maxBarSize={20}
                stroke="var(--surface-1)"
                strokeWidth={2}
              >
                <LabelList
                  dataKey="partnerships"
                  position="right"
                  style={{ fontSize: 12, fill: 'currentColor' }}
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </Section>
  )
}

function AuditTrail({ entries }: { entries: AuditEntry[] }) {
  return (
    <Section
      title="Audit trail"
      description="Every classification, score, fallback trigger, approval and override."
    >
      {entries.length === 0 ? (
        <Empty>Nothing logged yet.</Empty>
      ) : (
        <div className="max-h-[480px] space-y-2 overflow-y-auto">
          {entries.map((entry) => (
            <div key={entry.id} className="rounded-md border border-border p-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">{entry.action}</Badge>
                <span className="text-xs text-muted-foreground">{entry.actor_label}</span>
                <span className="text-xs text-muted-foreground">
                  {new Date(entry.created_at).toLocaleString()}
                </span>
                {entry.entity_type && (
                  <span className="text-xs text-muted-foreground">
                    {entry.entity_type} #{entry.entity_id}
                  </span>
                )}
              </div>
              {entry.reason && <p className="mt-1 text-xs">{entry.reason}</p>}
            </div>
          ))}
        </div>
      )}
    </Section>
  )
}
