import { RadialBar, RadialBarChart, PolarAngleAxis } from "recharts"

function colorFor(score: number): string {
  if (score >= 70) return "#16a34a"
  if (score >= 45) return "#d97706"
  return "#dc2626"
}

export function ScoreGauge({ score, size = 140 }: { score: number; size?: number }) {
  const color = colorFor(score)
  const data = [{ name: "score", value: score, fill: color }]
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <RadialBarChart
        width={size}
        height={size}
        cx="50%"
        cy="50%"
        innerRadius="72%"
        outerRadius="100%"
        barSize={10}
        data={data}
        startAngle={90}
        endAngle={-270}
      >
        <PolarAngleAxis type="number" domain={[0, 100]} angleAxisId={0} tick={false} />
        <RadialBar background={{ fill: "#f1f5f9" }} dataKey="value" cornerRadius={20} angleAxisId={0} />
      </RadialBarChart>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-bold text-slate-900">{score.toFixed(0)}</span>
        <span className="text-[11px] font-medium text-slate-400">/ 100</span>
      </div>
    </div>
  )
}
