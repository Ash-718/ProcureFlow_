import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { Plus, ArrowRight } from "lucide-react"
import { ChallengeApi } from "@/api/endpoints"
import { apiErrorMessage } from "@/api/client"
import type { Challenge } from "@/types"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { StatusBadge } from "@/components/ui/status-badge"
import { CardSkeletonGrid, EmptyState, ErrorState } from "@/components/ui/state-views"
import { formatDate } from "@/lib/utils"

export function GovChallengesPage() {
  const [challenges, setChallenges] = useState<Challenge[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  function load() {
    setError(null)
    setChallenges(null)
    ChallengeApi.list().then(setChallenges).catch((e) => setError(apiErrorMessage(e)))
  }

  useEffect(load, [])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Challenges</h1>
          <p className="text-sm text-slate-500">Problems your department has converted into procurement challenges.</p>
        </div>
        <Button asChild>
          <Link to="/gov/challenges/new">
            <Plus className="h-4 w-4" /> New Challenge
          </Link>
        </Button>
      </div>

      {error && <ErrorState message={error} onRetry={load} />}
      {!error && challenges === null && <CardSkeletonGrid />}
      {!error && challenges !== null && challenges.length === 0 && (
        <EmptyState
          title="No challenges yet"
          description="Convert a departmental problem into a structured, AI-matchable challenge."
          action={
            <Button asChild size="sm">
              <Link to="/gov/challenges/new"><Plus className="h-4 w-4" /> Create your first challenge</Link>
            </Button>
          }
        />
      )}
      {!error && challenges !== null && challenges.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {challenges.map((c) => (
            <Link key={c.id} to={`/gov/challenges/${c.id}`}>
              <Card className="h-full transition-shadow hover:shadow-md">
                <CardHeader>
                  <div className="flex items-start justify-between gap-2">
                    <CardTitle className="line-clamp-2">{c.title}</CardTitle>
                    <StatusBadge status={c.status} />
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  <p className="line-clamp-2 text-sm text-slate-500">{c.problemStatement}</p>
                  <div className="flex flex-wrap gap-1.5">
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">{c.domain}</span>
                    {c.publishedAt && (
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                        Published {formatDate(c.publishedAt)}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-1 text-sm font-medium text-brand-600">
                    View details <ArrowRight className="h-3.5 w-3.5" />
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
