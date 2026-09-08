import type { PilotKpiItem } from "@/types"

/**
 * KPI direction and achievement.
 *
 * These live outside the component module so importing them does not drag a
 * component in (and so React Fast Refresh keeps working cleanly).
 *
 * The direction rules mirror
 * `backend/app/services/recommendation_calculator.py` exactly. That matters:
 * the backend uses them to produce the performance and impact scores behind a
 * Scale/Modify/Reject recommendation, so if the UI disagreed it would colour a
 * genuinely good result as a miss — and contradict the recommendation shown
 * right beside it.
 */

/** A name containing one of these records an improvement: higher is better. */
const HIGHER_IS_BETTER_OVERRIDE = ["reduction", "increase", "gain", "improvement"]

/** Otherwise, a name containing one of these is lower-is-better. */
const LOWER_IS_BETTER = ["time", "delay", "latency", "rate"]

export function isLowerBetter(kpiName: string): boolean {
  const name = kpiName.toLowerCase()
  if (HIGHER_IS_BETTER_OVERRIDE.some((word) => name.includes(word))) return false
  return LOWER_IS_BETTER.some((word) => name.includes(word))
}

/**
 * Achievement in [0, 1], or `null` when the KPI cannot be assessed — no
 * target, a zero target, or no reading recorded yet.
 *
 * `null` is deliberately distinct from `0`: an unmeasured KPI is not a failed
 * one, and the backend excludes it from the averages for the same reason.
 */
export function kpiAchievement(kpi: PilotKpiItem): number | null {
  if (kpi.targetValue === null || kpi.targetValue === 0) return null
  if (kpi.latestRecordedValue === null) return null
  const ratio = isLowerBetter(kpi.kpiName)
    ? kpi.latestRecordedValue <= 0
      ? 1
      : kpi.targetValue / kpi.latestRecordedValue
    : kpi.latestRecordedValue / kpi.targetValue
  return Math.max(0, Math.min(1, ratio))
}

/**
 * How many assessable KPIs met target. `null` when none can be assessed, so
 * callers can say "no readings yet" rather than showing a misleading "0 of 0".
 */
export function kpiHealth(kpis: PilotKpiItem[]): { met: number; assessable: number } | null {
  const ratios = kpis.map(kpiAchievement).filter((ratio): ratio is number => ratio !== null)
  if (ratios.length === 0) return null
  return { met: ratios.filter((ratio) => ratio >= 1).length, assessable: ratios.length }
}
