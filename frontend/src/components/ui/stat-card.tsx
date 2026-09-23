import type { ReactNode } from "react"
import { Link } from "react-router-dom"
import { cn } from "@/lib/utils"

type Tone = "neutral" | "brand" | "success" | "warning" | "danger"

const TONE_ACCENT: Record<Tone, string> = {
  neutral: "text-slate-400",
  brand: "text-brand-600",
  success: "text-success-600",
  warning: "text-warning-600",
  danger: "text-danger-600",
}

const TONE_VALUE: Record<Tone, string> = {
  neutral: "text-slate-900",
  brand: "text-slate-900",
  success: "text-slate-900",
  warning: "text-warning-700",
  danger: "text-danger-700",
}

/**
 * A single headline number with its label.
 *
 * Deliberately flat — a thin border, no shadow, no gradient. A dashboard row
 * of these should read as a data strip, not as six competing cards. `tone`
 * escalates only for genuinely actionable counts (things overdue, decisions
 * pending); a count of zero should stay neutral, which is why callers pass the
 * tone conditionally rather than hardcoding it.
 *
 * Every value shown here comes from an API response. There is no placeholder
 * path: when data has not loaded the caller renders `StatCardSkeleton`, and
 * when a figure genuinely is zero it shows `0`.
 */
export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  tone = "neutral",
  to,
}: {
  label: string
  value: ReactNode
  hint?: string
  icon?: React.ComponentType<{ className?: string }>
  tone?: Tone
  /** Makes the whole card a link — use when there is an obvious next screen. */
  to?: string
}) {
  const body = (
    <>
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
        {Icon && <Icon className={cn("h-4 w-4 shrink-0", TONE_ACCENT[tone])} />}
      </div>
      <p className={cn("mt-2 text-2xl font-semibold tabular-nums", TONE_VALUE[tone])}>{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </>
  )

  const base =
    "rounded-lg border border-slate-200 bg-white p-4 transition-colors"

  if (to) {
    return (
      <Link to={to} className={cn(base, "block hover:border-brand-300 hover:bg-brand-50/40")}>
        {body}
      </Link>
    )
  }
  return <div className={base}>{body}</div>
}

export function StatCardSkeleton() {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="h-3 w-24 animate-pulse rounded bg-slate-200" />
      <div className="mt-3 h-7 w-12 animate-pulse rounded bg-slate-200" />
    </div>
  )
}

/** Responsive row of stat cards. Collapses 4 -> 2 -> 1 across breakpoints. */
export function StatGrid({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn("grid gap-3 sm:grid-cols-2 lg:grid-cols-4", className)}>{children}</div>
  )
}
