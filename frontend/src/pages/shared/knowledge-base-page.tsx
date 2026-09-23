import { useCallback, useEffect, useState } from "react"
import { Building2, Library, Search } from "lucide-react"
import { KnowledgeBaseApi } from "@/api/endpoints"
import { apiErrorMessage } from "@/api/client"
import type { KnowledgeBaseEntry } from "@/types"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PageHeader } from "@/components/ui/page-header"
import { StatusBadge } from "@/components/ui/status-badge"
import { CardSkeletonGrid, EmptyState, ErrorState } from "@/components/ui/state-views"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { formatDate } from "@/lib/utils"

/**
 * Institutional memory: what has already been tried, and how it turned out.
 *
 * The `success` filter is genuinely tri-state on the backend — `true` for a
 * scaled pilot, `false` for a rejected one, and `null` for one that was
 * modified or is undecided. The filter reflects that: "All outcomes" is the
 * only option that returns the null rows, and the wording avoids implying that
 * "not scaled" and "failed" are the same thing.
 */
export function KnowledgeBasePage() {
  const [entries, setEntries] = useState<KnowledgeBaseEntry[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState("")
  const [outcome, setOutcome] = useState<string>("all")

  const load = useCallback(
    (searchTerm: string, outcomeFilter: string) => {
      setError(null)
      setEntries(null)
      KnowledgeBaseApi.search({
        q: searchTerm || undefined,
        success: outcomeFilter === "all" ? undefined : outcomeFilter === "true",
      })
        .then(setEntries)
        .catch((err) => setError(apiErrorMessage(err)))
    },
    [],
  )

  useEffect(() => {
    load(query, outcome)
    // Re-runs when the outcome filter changes; free text is submitted
    // explicitly so typing does not fire a request per keystroke.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [outcome, load])

  const scaled = entries?.filter((entry) => entry.success === true).length ?? 0
  const notScaled = entries?.filter((entry) => entry.success === false).length ?? 0
  const modified = entries?.filter((entry) => entry.success === null).length ?? 0

  return (
    <div className="space-y-5">
      <PageHeader
        title="Knowledge base"
        description="Outcomes of completed pilots across departments. Before commissioning something new, see what has already been tried and what happened."
        meta={
          entries && (
            <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium tabular-nums text-slate-600">
              {entries.length} pilot{entries.length === 1 ? "" : "s"}
            </span>
          )
        }
      />

      <form
        onSubmit={(event) => {
          event.preventDefault()
          load(query, outcome)
        }}
        className="flex flex-wrap items-center gap-2"
        role="search"
      >
        <div className="relative min-w-[220px] flex-1">
          <Search
            className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
            aria-hidden
          />
          <Input
            className="pl-9"
            placeholder="Search by domain, technology, department or startup…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            aria-label="Search past pilots"
          />
        </div>
        <Select value={outcome} onValueChange={setOutcome}>
          <SelectTrigger className="w-44" aria-label="Filter by outcome">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All outcomes</SelectItem>
            <SelectItem value="true">Scaled</SelectItem>
            <SelectItem value="false">Rejected</SelectItem>
          </SelectContent>
        </Select>
        <Button type="submit" variant="outline">
          Search
        </Button>
      </form>

      {entries && entries.length > 0 && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-600">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-success-500" aria-hidden />
            {scaled} scaled
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-danger-500" aria-hidden />
            {notScaled} rejected
          </span>
          {modified > 0 && (
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-slate-400" aria-hidden />
              {modified} modified or undecided
            </span>
          )}
        </div>
      )}

      {error && <ErrorState message={error} onRetry={() => load(query, outcome)} />}
      {!error && entries === null && <CardSkeletonGrid count={2} />}
      {!error && entries?.length === 0 && (
        <EmptyState
          title="No matching pilots"
          description={
            outcome === "all"
              ? "No completed pilot matches that search. Entries are added here automatically when a pilot completes."
              : "No pilot with that outcome matches your search. Try 'All outcomes'."
          }
          action={
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setQuery("")
                setOutcome("all")
              }}
            >
              Clear filters
            </Button>
          }
        />
      )}

      {!error && entries && entries.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2">
          {entries.map((entry) => (
            <article
              key={entry.id}
              className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-5"
            >
              <div className="flex items-start justify-between gap-3">
                <h3 className="text-sm font-semibold leading-snug text-slate-900">
                  {entry.challengeTitle}
                </h3>
                {entry.success !== null ? (
                  <StatusBadge status={String(entry.success)} />
                ) : (
                  <Badge variant="neutral">Modified</Badge>
                )}
              </div>

              <p className="flex flex-wrap items-center gap-x-1.5 text-xs text-slate-500">
                <Building2 className="h-3.5 w-3.5" aria-hidden />
                {entry.departmentName}
                <span aria-hidden>·</span>
                <span className="font-medium text-slate-700">{entry.startupName}</span>
                <span aria-hidden>·</span>
                {formatDate(entry.createdAt)}
              </p>

              <div className="flex flex-wrap gap-1.5">
                <Badge variant="brand">{entry.domain}</Badge>
                {entry.technologyTags.map((tag) => (
                  <Badge key={tag} variant="outline">
                    {tag}
                  </Badge>
                ))}
              </div>

              {entry.outcomeSummary && (
                <div className="rounded-md bg-slate-50 p-3">
                  <p className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                    <Library className="h-3 w-3" aria-hidden /> What happened
                  </p>
                  <p className="text-sm leading-relaxed text-slate-700">
                    {entry.outcomeSummary}
                  </p>
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </div>
  )
}
