import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { ArrowRight, IndianRupee } from "lucide-react"
import { ChallengeApi } from "@/api/endpoints"
import { apiErrorMessage } from "@/api/client"
import type { Challenge } from "@/types"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { CardSkeletonGrid, EmptyState, ErrorState } from "@/components/ui/state-views"

export function StartupBrowseChallengesPage() {
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
      <div>
        <h1 className="text-xl font-bold text-slate-900">Browse Challenges</h1>
        <p className="text-sm text-slate-500">Published government challenges you can respond to with a proposal.</p>
      </div>

      {error && <ErrorState message={error} onRetry={load} />}
      {!error && challenges === null && <CardSkeletonGrid />}
      {!error && challenges?.length === 0 && (
        <EmptyState title="No published challenges right now" description="Check back soon — new challenges are published regularly." />
      )}
      {!error && challenges && challenges.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {challenges.map((c) => (
            <Link key={c.id} to={`/startup/challenges/${c.id}`}>
              <Card className="h-full transition-shadow hover:shadow-md">
                <CardHeader><CardTitle className="line-clamp-2">{c.title}</CardTitle></CardHeader>
                <CardContent className="space-y-3">
                  <p className="line-clamp-2 text-sm text-slate-500">{c.problemStatement}</p>
                  <div className="flex flex-wrap gap-1.5">
                    <Badge variant="brand">{c.domain}</Badge>
                    {c.desiredTechnology?.split(",").slice(0, 2).map((t) => (
                      <Badge key={t} variant="outline">{t.trim()}</Badge>
                    ))}
                  </div>
                  {c.budgetRange && (
                    <div className="flex items-center gap-1 text-xs text-slate-500">
                      <IndianRupee className="h-3.5 w-3.5" /> {c.budgetRange}
                    </div>
                  )}
                  <div className="flex items-center gap-1 text-sm font-medium text-brand-600">
                    View & respond <ArrowRight className="h-3.5 w-3.5" />
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
