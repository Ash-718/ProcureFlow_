import { useEffect, useState } from "react"
import { AdminApi } from "@/api/endpoints"
import { apiErrorMessage } from "@/api/client"
import type { AuditLogItem } from "@/types"
import { Badge } from "@/components/ui/badge"
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/state-views"
import { formatDateTime } from "@/lib/utils"

export function AdminAuditLogsPage() {
  const [logs, setLogs] = useState<AuditLogItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  function load() {
    setError(null)
    setLogs(null)
    AdminApi.auditLogs(0, 100).then((page) => setLogs(page.content)).catch((e) => setError(apiErrorMessage(e)))
  }
  useEffect(load, [])

  if (error) return <ErrorState message={error} onRetry={load} />
  if (!logs) return <LoadingState label="Loading audit logs…" />

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Audit Logs</h1>
        <p className="text-sm text-slate-500">Every state-changing action across the platform, most recent first.</p>
      </div>

      {logs.length === 0 ? (
        <EmptyState title="No activity yet" />
      ) : (
        <div className="space-y-2">
          {logs.map((log) => (
            <div key={log.id} className="flex items-center justify-between gap-4 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm">
              <div className="flex items-center gap-3">
                <Badge variant="outline">{log.action}</Badge>
                <span className="text-slate-600">{log.entityType}</span>
                {log.actorEmail && <span className="text-slate-400">by {log.actorEmail}</span>}
              </div>
              <span className="text-xs text-slate-400">{formatDateTime(log.createdAt)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
