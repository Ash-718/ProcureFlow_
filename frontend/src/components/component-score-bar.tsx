import { Progress } from "@/components/ui/progress"
import { cn } from "@/lib/utils"

function indicatorColor(score: number): string {
  if (score >= 70) return "bg-success-500"
  if (score >= 45) return "bg-warning-500"
  return "bg-danger-500"
}

export function ComponentScoreBar({
  label, value, weight,
}: { label: string; value: number; weight?: number }) {
  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between text-xs">
        <span className="font-medium text-slate-600">
          {label} {weight !== undefined && <span className="text-slate-400">({Math.round(weight * 100)}% weight)</span>}
        </span>
        <span className="font-semibold text-slate-800">{value.toFixed(0)}%</span>
      </div>
      <Progress value={value} indicatorClassName={cn(indicatorColor(value))} />
    </div>
  )
}
