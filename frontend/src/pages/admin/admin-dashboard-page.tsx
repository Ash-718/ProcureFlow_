import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { BookOpenCheck, ScrollText, ShieldCheck, UserX, Users } from "lucide-react"
import { AdminApi, KnowledgeBaseApi } from "@/api/endpoints"
import { apiErrorMessage } from "@/api/client"
import type { AdminUser, AuditLogItem, KnowledgeBaseEntry, Role } from "@/types"
import { PageHeader, SectionHeader } from "@/components/ui/page-header"
import { StatCard, StatCardSkeleton, StatGrid } from "@/components/ui/stat-card"
import { DataTable, type Column } from "@/components/ui/data-table"
import { EmptyState, ErrorState } from "@/components/ui/state-views"
import { ROLE_LABEL } from "@/components/layout/nav-config"
import { formatDateTime } from "@/lib/utils"

/**
 * Admin home — operational rather than decorative.
 *
 * Data:
 *   GET /admin/users                  -> accounts, roles, active state
 *   GET /admin/audit-logs?page=0      -> recent activity + total count
 *   GET /knowledge-base               -> institutional record size
 *
 * The audit total comes from the `Page` envelope's `totalElements`, so it is
 * the real row count rather than the length of the page fetched.
 */

interface DashboardData {
  users: AdminUser[]
  recent: AuditLogItem[]
  auditTotal: number
  knowledgeBase: KnowledgeBaseEntry[]
}

export function AdminDashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    setError(null)
    setData(null)
    Promise.all([
      AdminApi.listUsers(),
      AdminApi.auditLogs(0, 12),
      KnowledgeBaseApi.search({}),
    ])
      .then(([users, page, knowledgeBase]) =>
        setData({
          users,
          recent: page.content,
          auditTotal: page.totalElements,
          knowledgeBase,
        }),
      )
      .catch((err) => setError(apiErrorMessage(err)))
  }, [])

  useEffect(load, [load])

  const header = (
    <PageHeader
      title="Platform administration"
      description="Accounts, access and the audit record of every state-changing action on the platform."
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

  if (!data) {
    return (
      <div className="space-y-6">
        {header}
        <StatGrid>
          {Array.from({ length: 4 }).map((_, index) => (
            <StatCardSkeleton key={index} />
          ))}
        </StatGrid>
      </div>
    )
  }

  const { users, recent, auditTotal, knowledgeBase } = data
  const inactive = users.filter((user) => !user.active)

  const byRole = users.reduce<Record<string, number>>((accumulator, user) => {
    accumulator[user.role] = (accumulator[user.role] ?? 0) + 1
    return accumulator
  }, {})

  const columns: Column<AuditLogItem>[] = [
    {
      header: "Action",
      cell: (row) => (
        <span className="font-medium text-slate-900">{row.action.replaceAll("_", " ")}</span>
      ),
    },
    {
      header: "Entity",
      cell: (row) => row.entityType,
      hideOnMobile: true,
    },
    {
      header: "Actor",
      cell: (row) => row.actorEmail ?? <span className="text-slate-400">system</span>,
      hideOnMobile: true,
    },
    {
      header: "When",
      cell: (row) => formatDateTime(row.createdAt),
      className: "whitespace-nowrap text-right text-slate-500",
    },
  ]

  return (
    <div className="space-y-7">
      {header}

      <StatGrid>
        <StatCard label="Accounts" value={users.length} hint="Across all roles" icon={Users} to="/admin/users" />
        <StatCard
          label="Deactivated"
          value={inactive.length}
          hint={inactive.length > 0 ? "Cannot sign in" : "All accounts are active"}
          icon={UserX}
          tone={inactive.length > 0 ? "warning" : "neutral"}
          to="/admin/users"
        />
        <StatCard
          label="Audit entries"
          value={auditTotal.toLocaleString("en-IN")}
          hint="Append-only record"
          icon={ScrollText}
          to="/admin/audit-logs"
        />
        <StatCard
          label="Knowledge base"
          value={knowledgeBase.length}
          hint="Completed pilots recorded"
          icon={BookOpenCheck}
          to="/knowledge-base"
        />
      </StatGrid>

      <div className="grid gap-6 lg:grid-cols-[1fr_2fr]">
        <section className="space-y-3">
          <SectionHeader title="Accounts by role" icon={ShieldCheck} />
          <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
            {(Object.keys(ROLE_LABEL) as Role[]).map((role) => (
              <li key={role} className="flex items-center justify-between px-4 py-3">
                <span className="text-sm text-slate-700">{ROLE_LABEL[role]}</span>
                <span className="text-sm font-semibold tabular-nums text-slate-900">
                  {byRole[role] ?? 0}
                </span>
              </li>
            ))}
          </ul>
        </section>

        <section className="space-y-3">
          <SectionHeader
            title="Recent activity"
            icon={ScrollText}
            description="The newest entries in the append-only audit trail."
            actions={
              <Link
                to="/admin/audit-logs"
                className="text-xs font-medium text-brand-700 hover:underline"
              >
                View all
              </Link>
            }
          />
          <DataTable
            columns={columns}
            rows={recent}
            keyOf={(row) => row.id}
            caption="Most recent audit log entries"
            empty={<EmptyState title="No audit entries yet" />}
          />
        </section>
      </div>
    </div>
  )
}
