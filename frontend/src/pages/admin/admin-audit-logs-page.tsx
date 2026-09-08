import { useCallback, useEffect, useState } from "react"
import { ChevronLeft, ChevronRight } from "lucide-react"
import { AdminApi } from "@/api/endpoints"
import { apiErrorMessage } from "@/api/client"
import type { AuditLogItem, Page } from "@/types"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { PageHeader } from "@/components/ui/page-header"
import { DataTable, TableSkeleton, type Column } from "@/components/ui/data-table"
import { EmptyState, ErrorState } from "@/components/ui/state-views"
import { formatDateTime } from "@/lib/utils"

const PAGE_SIZE = 25

/**
 * The audit trail.
 *
 * Previously this fetched a single 100-row page and rendered it as a stack of
 * bordered rows — hard to scan and silently truncated at 100 regardless of how
 * many entries existed. It is now a real table with working pagination driven
 * by the `Page<T>` envelope the API already returns, so the total count is
 * accurate and every entry is reachable.
 */
export function AdminAuditLogsPage() {
  const [page, setPage] = useState(0)
  const [data, setData] = useState<Page<AuditLogItem> | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    setError(null)
    setData(null)
    AdminApi.auditLogs(page, PAGE_SIZE)
      .then(setData)
      .catch((err) => setError(apiErrorMessage(err)))
  }, [page])

  useEffect(load, [load])

  const columns: Column<AuditLogItem>[] = [
    {
      header: "Action",
      cell: (row) => <Badge variant="outline">{row.action.replaceAll("_", " ")}</Badge>,
    },
    {
      header: "Entity",
      cell: (row) => <span className="text-slate-700">{row.entityType}</span>,
    },
    {
      header: "Actor",
      cell: (row) =>
        row.actorEmail ?? <span className="text-slate-400">system</span>,
      hideOnMobile: true,
    },
    {
      header: "Reference",
      cell: (row) =>
        row.entityId ? (
          <code className="rounded bg-slate-50 px-1.5 py-0.5 text-[11px] text-slate-500">
            {row.entityId.slice(0, 8)}
          </code>
        ) : (
          <span className="text-slate-300">—</span>
        ),
      hideOnMobile: true,
    },
    {
      header: "When",
      cell: (row) => formatDateTime(row.createdAt),
      className: "whitespace-nowrap text-right text-slate-500",
    },
  ]

  const header = (
    <PageHeader
      title="Audit trail"
      description="Every state-changing action on the platform, newest first. Entries are append-only and are never edited or removed."
      meta={
        data && (
          <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium tabular-nums text-slate-600">
            {data.totalElements.toLocaleString("en-IN")} entries
          </span>
        )
      }
    />
  )

  if (error) {
    return (
      <div className="space-y-6">
        {header}
        <ErrorState message={error} onRetry={load} />
      </div>
    )
  }

  return (
    <div className="space-y-5">
      {header}

      {!data ? (
        <TableSkeleton rows={8} columns={5} />
      ) : (
        <>
          <DataTable
            columns={columns}
            rows={data.content}
            keyOf={(row) => row.id}
            caption="Platform audit log"
            empty={
              <EmptyState
                title="No activity recorded yet"
                description="Actions such as signing in, publishing a challenge or recording a decision appear here."
              />
            }
          />

          {data.totalPages > 1 && (
            <nav
              className="flex items-center justify-between gap-3"
              aria-label="Audit log pagination"
            >
              <p className="text-xs text-slate-500">
                Page {data.number + 1} of {data.totalPages} · showing{" "}
                {data.content.length} of{" "}
                {data.totalElements.toLocaleString("en-IN")}
              </p>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={data.number === 0}
                  onClick={() => setPage((current) => Math.max(0, current - 1))}
                >
                  <ChevronLeft className="h-4 w-4" /> Previous
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={data.number >= data.totalPages - 1}
                  onClick={() => setPage((current) => current + 1)}
                >
                  Next <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </nav>
          )}
        </>
      )}
    </div>
  )
}
