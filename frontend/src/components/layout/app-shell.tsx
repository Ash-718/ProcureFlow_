import { NavLink, Outlet } from "react-router-dom"
import { LogOut, Building2 } from "lucide-react"
import { useAuth } from "@/hooks/useAuth"
import { NAV_BY_ROLE, ROLE_LABEL } from "./nav-config"
import { NotificationBell } from "./notification-bell"
import { cn } from "@/lib/utils"

export function AppShell() {
  const { user, logout } = useAuth()
  if (!user) return null

  const navItems = NAV_BY_ROLE[user.role]

  return (
    <div className="flex min-h-screen bg-slate-50">
      <aside className="flex w-64 flex-col border-r border-slate-200 bg-white">
        <div className="flex items-center gap-2 border-b border-slate-100 px-5 py-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-white">
            <Building2 className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm font-bold leading-tight text-slate-900">INNOVATE-GOV</p>
            <p className="text-[11px] text-slate-400">SIH26136</p>
          </div>
        </div>

        <nav className="flex-1 space-y-1 px-3 py-4">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  isActive ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100"
                )
              }
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-slate-100 p-3">
          <div className="flex items-center justify-between rounded-lg px-2 py-2">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-slate-800">{user.fullName}</p>
              <p className="text-xs text-slate-400">{ROLE_LABEL[user.role]}</p>
            </div>
            <button
              onClick={logout}
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              aria-label="Log out"
              title="Log out"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      <div className="flex flex-1 flex-col">
        <header className="flex h-14 items-center justify-end gap-3 border-b border-slate-200 bg-white px-6">
          <NotificationBell />
        </header>
        <main className="flex-1 overflow-y-auto px-8 py-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
