import { useEffect, useState } from "react"
import { AdminApi } from "@/api/endpoints"
import { apiErrorMessage } from "@/api/client"
import type { AdminUser } from "@/types"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ErrorState, LoadingState } from "@/components/ui/state-views"
import { formatDate } from "@/lib/utils"

export function AdminUsersPage() {
  const [users, setUsers] = useState<AdminUser[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  function load() {
    setError(null)
    setUsers(null)
    AdminApi.listUsers().then(setUsers).catch((e) => setError(apiErrorMessage(e)))
  }
  useEffect(load, [])

  async function toggleActive(user: AdminUser) {
    const updated = await AdminApi.setActive(user.id, !user.active)
    setUsers((prev) => prev?.map((u) => (u.id === user.id ? updated : u)) ?? null)
  }

  if (error) return <ErrorState message={error} onRetry={load} />
  if (!users) return <LoadingState label="Loading users…" />

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Users</h1>
        <p className="text-sm text-slate-500">{users.length} accounts across all roles.</p>
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-400">
              <th className="p-4">Name</th>
              <th className="p-4">Email</th>
              <th className="p-4">Role</th>
              <th className="p-4">Joined</th>
              <th className="p-4">Status</th>
              <th className="p-4"></th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-b border-slate-100 last:border-0">
                <td className="p-4 font-medium text-slate-800">{u.fullName}</td>
                <td className="p-4 text-slate-600">{u.email}</td>
                <td className="p-4"><Badge variant="brand">{u.role}</Badge></td>
                <td className="p-4 text-slate-500">{formatDate(u.createdAt)}</td>
                <td className="p-4">
                  <Badge variant={u.active ? "success" : "danger"}>{u.active ? "Active" : "Deactivated"}</Badge>
                </td>
                <td className="p-4">
                  <Button size="sm" variant="outline" onClick={() => toggleActive(u)}>
                    {u.active ? "Deactivate" : "Activate"}
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
