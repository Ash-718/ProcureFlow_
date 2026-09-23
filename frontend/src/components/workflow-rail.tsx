import { Check } from "lucide-react"
import { LIFECYCLE_STAGES, type LifecycleStage } from "@/lib/lifecycle"
import { cn } from "@/lib/utils"

/**
 * The procurement lifecycle, drawn as a rail.
 *
 * This exists because the platform's value is the *pipeline* — a government
 * problem becoming a structured challenge, matched, evaluated, piloted,
 * measured, and finally decided on. Without this, a visitor sees a set of
 * unrelated CRUD screens and has to be told what the product does.
 *
 * The stage shown as current is derived from real record state (a challenge's
 * status, a pilot's status, whether a recommendation has a human decision) —
 * never from a hardcoded step number.
 */

export function WorkflowRail({
  current,
  className,
  compact = false,
}: {
  current: LifecycleStage
  className?: string
  /** Drops the labels, leaving just the dotted rail — for use inside a card. */
  compact?: boolean
}) {
  const currentIndex = LIFECYCLE_STAGES.findIndex((stage) => stage.key === current)

  return (
    <ol
      className={cn(
        "flex w-full items-center overflow-x-auto",
        compact ? "gap-0" : "gap-0 pb-1",
        className,
      )}
      aria-label="Procurement lifecycle"
    >
      {LIFECYCLE_STAGES.map((stage, index) => {
        const done = index < currentIndex
        const active = index === currentIndex
        return (
          <li
            key={stage.key}
            className="flex min-w-0 flex-1 items-center"
            aria-current={active ? "step" : undefined}
          >
            <div className="flex min-w-0 flex-col items-center gap-1.5">
              <span
                className={cn(
                  "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-[10px] font-semibold transition-colors",
                  done && "border-brand-600 bg-brand-600 text-white",
                  active && "border-brand-600 bg-white text-brand-700 ring-2 ring-brand-200",
                  !done && !active && "border-slate-300 bg-white text-slate-400",
                )}
              >
                {done ? <Check className="h-3 w-3" aria-hidden /> : index + 1}
              </span>
              {!compact && (
                <span
                  className={cn(
                    "max-w-[5.5rem] truncate text-center text-[10px] leading-tight",
                    active ? "font-semibold text-brand-700" : "text-slate-500",
                  )}
                  title={stage.label}
                >
                  {stage.label}
                </span>
              )}
            </div>
            {index < LIFECYCLE_STAGES.length - 1 && (
              <span
                aria-hidden
                className={cn(
                  "mx-1 h-px flex-1",
                  index < currentIndex ? "bg-brand-500" : "bg-slate-200",
                )}
              />
            )}
          </li>
        )
      })}
    </ol>
  )
}
