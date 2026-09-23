import { Check, CircleDashed, Clock, TriangleAlert } from "lucide-react"
import type { MilestoneStatus, PilotMilestoneItem } from "@/types"
import { cn, formatDate } from "@/lib/utils"

/**
 * Pilot milestones as a vertical timeline.
 *
 * A timeline rather than a table because milestones are sequential and the
 * question being asked is "where is this pilot, and is anything slipping?" —
 * which a list of rows answers poorly.
 *
 * Status is carried by an icon *and* a label as well as colour, so the state
 * is legible without relying on colour perception.
 */

const STATUS_STYLE: Record<
  MilestoneStatus,
  { icon: React.ComponentType<{ className?: string }>; dot: string; label: string; text: string }
> = {
  DONE: {
    icon: Check,
    dot: "border-success-500 bg-success-500 text-white",
    label: "Done",
    text: "text-success-700",
  },
  IN_PROGRESS: {
    icon: Clock,
    dot: "border-brand-500 bg-white text-brand-600",
    label: "In progress",
    text: "text-brand-700",
  },
  DELAYED: {
    icon: TriangleAlert,
    dot: "border-warning-500 bg-warning-50 text-warning-600",
    label: "Delayed",
    text: "text-warning-700",
  },
  PENDING: {
    icon: CircleDashed,
    dot: "border-slate-300 bg-white text-slate-400",
    label: "Pending",
    text: "text-slate-500",
  },
}

export function MilestoneTimeline({ milestones }: { milestones: PilotMilestoneItem[] }) {
  if (milestones.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">
        No milestones were defined for this pilot.
      </p>
    )
  }

  return (
    <ol className="relative space-y-0">
      {milestones.map((milestone, index) => {
        const style = STATUS_STYLE[milestone.status] ?? STATUS_STYLE.PENDING
        const Icon = style.icon
        const last = index === milestones.length - 1
        return (
          <li key={milestone.id} className="relative flex gap-3 pb-5 last:pb-0">
            {!last && (
              <span
                aria-hidden
                className="absolute left-[11px] top-6 h-full w-px bg-slate-200"
              />
            )}
            <span
              className={cn(
                "relative z-10 mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2",
                style.dot,
              )}
            >
              <Icon className="h-3 w-3" aria-hidden />
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
                <p className="text-sm font-medium text-slate-900">{milestone.title}</p>
                <span className={cn("text-xs font-medium", style.text)}>{style.label}</span>
              </div>
              <p className="mt-0.5 text-xs text-slate-500">
                {milestone.dueDate ? `Due ${formatDate(milestone.dueDate)}` : "No due date"}
                {milestone.completionDate &&
                  ` · Completed ${formatDate(milestone.completionDate)}`}
              </p>
            </div>
          </li>
        )
      })}
    </ol>
  )
}
