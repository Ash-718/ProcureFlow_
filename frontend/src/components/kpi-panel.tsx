import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, XAxis, YAxis } from "recharts"
import { Target } from "lucide-react"
import type { PilotKpiItem } from "@/types"
import { isLowerBetter, kpiAchievement } from "@/lib/kpi"
import { cn, formatDateTime, formatScore } from "@/lib/utils"

/**
 * KPI target-vs-actual for a pilot.
 *
 * Two things this deliberately does *not* do:
 *
 * 1. It does not draw a trend line. The API exposes only the latest reading
 *    per KPI (`latestRecordedValue`), not the history behind it, so a
 *    time-series chart would be inventing points. A KPI with no reading yet
 *    shows "Not yet recorded", not a zero.
 * 2. It does not assume higher is better. The backend's recommendation engine
 *    infers direction from the KPI's name; `lib/kpi.ts` mirrors that rule so
 *    the bar colour agrees with the score the engine produced. Getting this
 *    wrong would paint a genuinely good result red.
 */

export function KpiPanel({ kpis }: { kpis: PilotKpiItem[] }) {
  if (kpis.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">
        No KPIs were defined for this pilot.
      </p>
    )
  }

  const measured = kpis.filter((k) => k.latestRecordedValue !== null && k.targetValue !== null)

  const chartData = measured.map((kpi) => {
    const achievement = kpiAchievement(kpi) ?? 0
    return {
      name: kpi.kpiName.length > 22 ? `${kpi.kpiName.slice(0, 21)}…` : kpi.kpiName,
      percent: Math.round(achievement * 100),
      met: achievement >= 1,
    }
  })

  return (
    <div className="space-y-4">
      {chartData.length > 0 && (
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <p className="mb-3 text-xs font-medium uppercase tracking-wide text-slate-500">
            Achievement against target
          </p>
          {/* Fixed row height per KPI keeps the chart legible and stops it
              collapsing on narrow screens. */}
          <div style={{ height: Math.max(chartData.length * 42, 100) }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} layout="vertical" margin={{ left: 0, right: 44 }}>
                <XAxis type="number" domain={[0, 100]} hide />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={150}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fontSize: 11, fill: "#475569" }}
                />
                <Bar dataKey="percent" radius={[0, 3, 3, 0]} barSize={16} isAnimationActive={false}>
                  {chartData.map((entry, index) => (
                    <Cell key={index} fill={entry.met ? "#2e7d44" : "#b7791f"} />
                  ))}
                  <LabelList
                    dataKey="percent"
                    position="right"
                    // Recharts types the label as possibly-undefined text, so
                    // the formatter has to accept that rather than `number`.
                    formatter={(value: unknown) =>
                      value === undefined || value === null ? "" : `${value}%`
                    }
                    style={{ fontSize: 11, fill: "#334155" }}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p className="mt-2 text-[11px] text-slate-500">
            Capped at 100%. Green means the target was met or exceeded.
          </p>
        </div>
      )}

      <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
        {kpis.map((kpi) => {
          const achievement = kpiAchievement(kpi)
          const recorded = kpi.latestRecordedValue !== null
          return (
            <li key={kpi.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3">
              <div className="min-w-0 flex-1">
                <p className="flex items-center gap-1.5 text-sm font-medium text-slate-900">
                  <Target className="h-3.5 w-3.5 shrink-0 text-slate-400" aria-hidden />
                  {kpi.kpiName}
                  {isLowerBetter(kpi.kpiName) && (
                    <span
                      className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-normal text-slate-500"
                      title="For this KPI a lower recorded value is better"
                    >
                      lower is better
                    </span>
                  )}
                </p>
                {recorded && kpi.latestRecordedAt && (
                  <p className="mt-0.5 text-[11px] text-slate-500">
                    Last recorded {formatDateTime(kpi.latestRecordedAt)}
                  </p>
                )}
              </div>

              <div className="flex items-baseline gap-1.5 text-sm tabular-nums">
                <span className="text-slate-500">Target</span>
                <span className="font-medium text-slate-800">
                  {formatScore(kpi.targetValue, 0)}
                  {kpi.unit ? ` ${kpi.unit}` : ""}
                </span>
              </div>

              <div className="flex items-baseline gap-1.5 text-sm tabular-nums">
                <span className="text-slate-500">Actual</span>
                {recorded ? (
                  <span
                    className={cn(
                      "font-semibold",
                      achievement === null
                        ? "text-slate-800"
                        : achievement >= 1
                          ? "text-success-700"
                          : "text-warning-700",
                    )}
                  >
                    {formatScore(kpi.latestRecordedValue, 0)}
                    {kpi.unit ? ` ${kpi.unit}` : ""}
                  </span>
                ) : (
                  <span className="text-slate-400">Not yet recorded</span>
                )}
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
