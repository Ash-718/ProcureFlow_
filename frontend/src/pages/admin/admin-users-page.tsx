import { useCallback, useEffect, useState } from "react"
import { Loader2 } from "lucide-react"
import { AdminApi } from "@/api/endpoints"
import { apiErrorMessage } from "@/api/client"
import type { AdminUser } from "@/types"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { PageHeader } from "@/components/ui/page-header"
import { DataTable, TableSkeleton, type Column } from "@/components/ui/data-table"
import { EmptyState, ErrorState } from "@/components/ui/state-views"
import { ROLE_LABEL } from "@/components/layout/nav-config"
import { formatDate } from "@/lib/utils"

/**
 * Account administration.
 *
 * Same two endpoints as before. What changed: the hand-rolled table is now the
 * shared `DataTable` (so it scrolls rather than overflowing the page on
 * mobile, and secondary columns drop out below `md`), the activate/deactivate
 * action reports failures instead of silently swallowing them, and the button
 * shows its pending state.
 */
export function AdminUsersPage() {
  const [users, setUsers] = useState<AdminUser[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [pendingId, setPendingId] = useState<string | null>(null)

  const load = useCallback(() => {
    setError(null)
    setUsers(null)
    AdminApi.listUsers()
      .then(setUsers)
      .catch((err) => setError(apiErrorMessage(err)))
  }, [])

  useEffect(load, [load])

  async function toggleActive(user: AdminUser) {
    setActionError(null)
    setPendingId(user.id)
    try {
      const updated = await AdminApi.setActive(user.id, !user.active)
      setUsers(
        (previous) =>
          previous?.map((candidate) => (candidate.id === user.id ? updated : candidate)) ?? null,
      )
    } catch (err) {
      // Previously this rejection was unhandled, so a failed change left the
      // row looking unchanged with no explanation.
      setActionError(apiErrorMessage(err))
    } finally {
      setPendingId(null)
    }
  }

  const columns: Column<AdminUser>[] = [
    {
      header: "Name",
      cell: (row) => <span className="font-medium text-slate-900">{row.fullName}</span>,
    },
    {
      header: "Email",
      cell: (row) => <span className="text-slate-600">{row.email}</span>,
      hideOnMobile: true,
    },
    {
      header: "Role",
      cell: (row) => <Badge variant="brand">{ROLE_LABEL[row.role]}</Badge>,
    },
    {
      header: "Joined",
      cell: (row) => formatDate(row.createdAt),
      className: "whitespace-nowrap text-slate-500",
      hideOnMobile: true,
    },
    {
      header: "Status",
      cell: (row) => (
        <Badge variant={row.active ? "success" : "danger"}>
          {row.active ? "Active" : "Deactivated"}
        </Badge>
      ),
    },
    {
      header: "Access",
      className: "text-right",
      cell: (row) => (
        <Button
          size="sm"
          variant="outline"
          disabled={pendingId === row.id}
          onClick={() => toggleActive(row)}
          aria-label={`${row.active ? "Deactivate" : "Activate"} ${row.fullName}`}
        >
          {pendingId === row.id ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : row.active ? (
            "Deactivate"
          ) : (
            "Activate"
          )}
        </Button>
      ),
    },
  ]

  const header = (
    <PageHeader
      title="Accounts"
      description="Every account on the platform. Deactivating an account takes effect on its next request."
      meta={
        users && (
          <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium tabular-nums text-slate-600">
            {users.length} accounts
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
      {actionError && <ErrorState message={actionError} />}
      {!users ? (
        <TableSkeleton rows={8} columns={6} />
      ) : (
        <DataTable
          columns={columns}
          rows={users}
          keyOf={(row) => row.id}
          caption="Platform user accounts"
          empty={<EmptyState title="No accounts found" />}
        />
      )}
    </div>
  )
}
