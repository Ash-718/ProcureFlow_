import { useEffect, useState } from "react"
import { Search } from "lucide-react"
import { KnowledgeBaseApi } from "@/api/endpoints"
import { apiErrorMessage } from "@/api/client"
import type { KnowledgeBaseEntry } from "@/types"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { StatusBadge } from "@/components/ui/status-badge"
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/state-views"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

export function KnowledgeBasePage() {
  const [entries, setEntries] = useState<KnowledgeBaseEntry[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [q, setQ] = useState("")
  const [success, setSuccess] = useState<string>("all")

  function load() {
    setError(null)
    KnowledgeBaseApi.search({ q: q || undefined, success: success === "all" ? undefined : success === "true" })
      .then(setEntries)
      .catch((e) => setError(apiErrorMessage(e)))
  }

  useEffect(load, []) // eslint-disable-line react-hooks/exhaustive-deps

  function onSearchSubmit(e: React.FormEvent) {
    e.preventDefault()
    setEntries(null)
    load()
  }

  const scaled = entries?.filter((e) => e.success === true).length ?? 0
  const rejected = entries?.filter((e) => e.success === false).length ?? 0

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Knowledge Base of Past Pilots</h1>
        <p className="text-sm text-slate-500">Searchable outcomes from every completed pilot, across departments.</p>
      </div>

      <form onSubmit={onSearchSubmit} className="flex flex-wrap gap-2">
        <div className="relative flex-1 min-w-[240px]">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input className="pl-9" placeholder="Search domain, technology, department…" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <Select value={success} onValueChange={setSuccess}>
          <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All outcomes</SelectItem>
            <SelectItem value="true">Scaled</SelectItem>
            <SelectItem value="false">Not scaled</SelectItem>
          </SelectContent>
        </Select>
      </form>

      {entries && entries.length > 0 && (
        <div className="flex gap-3 text-sm text-slate-500">
          <span>{entries.length} pilot(s) found</span>
          <span>·</span>
          <span className="text-success-600">{scaled} scaled</span>
          <span>·</span>
          <span className="text-danger-600">{rejected} rejected</span>
        </div>
      )}

      {error && <ErrorState message={error} onRetry={load} />}
      {!error && entries === null && <LoadingState label="Searching knowledge base…" />}
      {!error && entries?.length === 0 && <EmptyState title="No matching pilots" description="Try a different search term or filter." />}

      {!error && entries && entries.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2">
          {entries.map((e) => (
            <Card key={e.id}>
              <CardHeader>
                <div className="flex items-start justify-between gap-2">
                  <CardTitle className="line-clamp-2">{e.challengeTitle}</CardTitle>
                  {e.success !== null && <StatusBadge status={String(e.success)} />}
                </div>
              </CardHeader>
              <CardContent className="space-y-2">
                <p className="text-xs text-slate-500">{e.departmentName} · {e.startupName}</p>
                <div className="flex flex-wrap gap-1.5">
                  <Badge variant="brand">{e.domain}</Badge>
                  {e.technologyTags.map((t) => <Badge key={t} variant="outline">{t}</Badge>)}
                </div>
                {e.outcomeSummary && <p className="line-clamp-3 text-sm text-slate-600">{e.outcomeSummary}</p>}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
