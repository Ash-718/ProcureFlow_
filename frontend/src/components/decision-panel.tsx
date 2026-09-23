import type { ReactNode } from "react"
import { Cpu, Landmark, MinusCircle } from "lucide-react"
import type { Recommendation, RecommendationType } from "@/types"
import { cn, formatDateTime, formatScore } from "@/lib/utils"

/**
 * Scale / Modify / Reject — the system's recommendation beside the human's
 * decision.
 *
 * The layout is the argument: two separate panels, side by side, each labelled
 * with who produced it. They are never merged into a single verdict, and the
 * human panel is rendered even when no decision has been taken — showing
 * "Awaiting decision" rather than quietly falling back to the system value.
 * The database keeps these as two columns for exactly this reason, and the UI
 * has to make that visible: the engine advises, the department decides.
 *
 * Every number here comes from `GET /pilots/{id}/recommendation`.
 */

const DECISION_TONE: Record<RecommendationType, string> = {
  SCALE: "border-success-500 bg-success-50 text-success-700",
  MODIFY: "border-warning-500 bg-warning-50 text-warning-700",
  REJECT: "border-danger-500 bg-danger-50 text-danger-700",
}

const DECISION_MEANING: Record<RecommendationType, string> = {
  SCALE: "Roll the solution out more widely",
  MODIFY: "Continue with changes before scaling",
  REJECT: "Do not proceed with this solution",
}

function DecisionValue({ decision }: { decision: RecommendationType }) {
  return (
    <div className="space-y-1">
      <span
        className={cn(
          "inline-flex items-center rounded-md border px-2.5 py-1 text-base font-semibold tracking-tight",
          DECISION_TONE[decision],
        )}
      >
        {decision}
      </span>
      <p className="text-xs text-slate-600">{DECISION_MEANING[decision]}</p>
    </div>
  )
}

function Panel({
  icon: Icon,
  eyebrow,
  attribution,
  children,
  tone = "default",
}: {
  icon: React.ComponentType<{ className?: string }>
  eyebrow: string
  attribution: string
  children: ReactNode
  tone?: "default" | "machine"
}) {
  return (
    <div
      className={cn(
        "flex-1 rounded-lg border p-4",
        tone === "machine"
          ? "border-accent-100 bg-accent-50/60"
          : "border-slate-200 bg-white",
      )}
    >
      <div className="mb-2.5 flex items-center gap-1.5">
        <Icon
          className={cn(
            "h-3.5 w-3.5",
            tone === "machine" ? "text-accent-600" : "text-brand-600",
          )}
          aria-hidden
        />
        <p
          className={cn(
            "text-[11px] font-semibold uppercase tracking-wide",
            tone === "machine" ? "text-accent-700" : "text-brand-700",
          )}
        >
          {eyebrow}
        </p>
      </div>
      {children}
      <p className="mt-3 border-t border-slate-100 pt-2 text-[11px] text-slate-500">
        {attribution}
      </p>
    </div>
  )
}

export function DecisionPanel({
  recommendation,
  action,
}: {
  recommendation: Recommendation
  /** The decision control, rendered only for roles allowed to decide. */
  action?: ReactNode
}) {
  const decided = recommendation.finalDecision !== null
  const overrode =
    decided && recommendation.finalDecision !== recommendation.recommendation

  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-3 sm:flex-row">
        <Panel
          icon={Cpu}
          eyebrow="System recommendation"
          attribution={`Generated ${formatDateTime(recommendation.generatedAt)} from recorded KPI results and milestone adherence.`}
          tone="machine"
        >
          <DecisionValue decision={recommendation.recommendation} />
          <dl className="mt-3 grid grid-cols-3 gap-2">
            {[
              ["Cost", recommendation.costScore],
              ["Performance", recommendation.performanceScore],
              ["Impact", recommendation.impactScore],
            ].map(([label, score]) => (
              <div key={label as string}>
                <dt className="text-[10px] uppercase tracking-wide text-slate-500">
                  {label}
                </dt>
                <dd className="text-sm font-semibold tabular-nums text-slate-800">
                  {formatScore(score as number, 2)}
                </dd>
              </div>
            ))}
          </dl>
        </Panel>

        <Panel
          icon={Landmark}
          eyebrow="Final decision"
          attribution={
            decided
              ? `Recorded by ${recommendation.reviewedByName ?? "the department"} on ${formatDateTime(recommendation.decidedAt)}.`
              : "The department has authority over the outcome. The recommendation above is advisory."
          }
        >
          {decided && recommendation.finalDecision ? (
            <DecisionValue decision={recommendation.finalDecision} />
          ) : (
            <div className="space-y-1">
              <span className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-slate-50 px-2.5 py-1 text-base font-semibold text-slate-500">
                <MinusCircle className="h-4 w-4" aria-hidden />
                Awaiting decision
              </span>
              <p className="text-xs text-slate-600">No decision has been recorded yet</p>
            </div>
          )}
          {action && <div className="mt-3">{action}</div>}
        </Panel>
      </div>

      {overrode && (
        <p className="rounded-md border border-warning-100 bg-warning-50 px-3 py-2 text-xs text-warning-700">
          The department recorded <strong>{recommendation.finalDecision}</strong> where the
          system recommended <strong>{recommendation.recommendation}</strong>. Both are
          retained on the record.
        </p>
      )}

      {recommendation.rationaleText && (
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <p className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-accent-700">
            <Cpu className="h-3.5 w-3.5" aria-hidden /> How the system reached this
          </p>
          <p className="text-sm leading-relaxed text-slate-700">
            {recommendation.rationaleText}
          </p>
        </div>
      )}
    </div>
  )
}
