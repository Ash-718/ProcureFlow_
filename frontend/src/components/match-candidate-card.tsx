import { CheckCircle2, AlertTriangle, UserSearch } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { ScoreGauge } from "@/components/score-gauge"
import { ComponentScoreBar } from "@/components/component-score-bar"

export interface NormalizedMatch {
  startupId: string
  companyName: string
  rank: number
  overallScore: number
  semanticSimilarity: number
  technologyMatch: number
  domainMatch: number
  experienceScore: number
  readinessScore: number
  reasons: string[]
  gaps: string[]
}

export function MatchCandidateCard({
  match, onViewProfile, actions,
}: { match: NormalizedMatch; onViewProfile: (startupId: string) => void; actions?: React.ReactNode }) {
  return (
    <Card>
      <CardContent className="grid gap-5 p-5 md:grid-cols-[auto_1fr_1fr]">
        <div className="flex flex-col items-center justify-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">Rank #{match.rank}</span>
          <ScoreGauge score={match.overallScore} size={110} />
        </div>

        <div className="space-y-3">
          <div>
            <h4 className="text-base font-semibold text-slate-900">{match.companyName}</h4>
            <button onClick={() => onViewProfile(match.startupId)} className="flex items-center gap-1 text-xs font-medium text-brand-600 hover:underline">
              <UserSearch className="h-3.5 w-3.5" /> View full profile
            </button>
          </div>
          <div className="space-y-2">
            <ComponentScoreBar label="Semantic similarity" value={match.semanticSimilarity} weight={0.35} />
            <ComponentScoreBar label="Technology match" value={match.technologyMatch} weight={0.20} />
            <ComponentScoreBar label="Domain match" value={match.domainMatch} weight={0.15} />
            <ComponentScoreBar label="Experience" value={match.experienceScore} weight={0.15} />
            <ComponentScoreBar label="Pilot readiness" value={match.readinessScore} weight={0.15} />
          </div>
        </div>

        <div className="space-y-3">
          <div>
            <p className="mb-1 flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-success-700">
              <CheckCircle2 className="h-3.5 w-3.5" /> Why this match
            </p>
            <ul className="space-y-1">
              {match.reasons.map((r, i) => (
                <li key={i} className="flex gap-1.5 text-sm text-slate-600">
                  <span className="text-success-500">•</span> {r}
                </li>
              ))}
            </ul>
          </div>
          {match.gaps.length > 0 && (
            <div>
              <p className="mb-1 flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-warning-700">
                <AlertTriangle className="h-3.5 w-3.5" /> Potential gaps
              </p>
              <ul className="space-y-1">
                {match.gaps.map((g, i) => (
                  <li key={i} className="flex gap-1.5 text-sm text-slate-600">
                    <span className="text-warning-500">•</span> {g}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {actions && <div className="flex gap-2 pt-1">{actions}</div>}
        </div>
      </CardContent>
    </Card>
  )
}
