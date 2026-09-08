import { useEffect, useState } from "react"
import { NavLink, Outlet, useLocation } from "react-router-dom"
import { Building2, LogOut, Menu, PanelLeftClose, PanelLeft, X } from "lucide-react"
import { useAuth } from "@/hooks/useAuth"
import { NAV_BY_ROLE, ROLE_LABEL, ROLE_TAGLINE } from "./nav-config"
import { NotificationBell } from "./notification-bell"
import { cn } from "@/lib/utils"

/**
 * Application shell: masthead, role-aware sidebar, content region.
 *
 * Three things this handles that the previous shell did not:
 *
 * - **Responsive.** The sidebar was a fixed 16rem column with no mobile
 *   handling. It now collapses to icons on `lg` and becomes an off-canvas
 *   drawer below that, so the app is usable on a tablet or phone rather than
 *   merely shrunken.
 * - **A real header.** The header held only a notification bell. It now
 *   carries the platform identity and the signed-in user, which is where a
 *   government user expects to confirm who they are acting as.
 * - **Role identity.** Each role is a distinct workspace, so the sidebar
 *   states the role and what it is for rather than leaving it implied.
 */
export function AppShell() {
  const { user, logout } = useAuth()
  const location = useLocation()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(false)

  // Close the drawer on navigation — otherwise it stays over the page the
  // user just asked for.
  useEffect(() => {
    setMobileOpen(false)
  }, [location.pathname])

  // Escape closes the drawer, matching the dialog behaviour elsewhere.
  useEffect(() => {
    if (!mobileOpen) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMobileOpen(false)
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [mobileOpen])

  if (!user) return null

  const groups = NAV_BY_ROLE[user.role]

  const sidebar = (
    <div className="flex h-full flex-col bg-white">
      <div
        className={cn(
          "flex h-14 items-center gap-2.5 border-b border-slate-200 px-4",
          collapsed && "lg:justify-center lg:px-0",
        )}
      >
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-brand-700 text-white">
          <Building2 className="h-4.5 w-4.5" aria-hidden />
        </div>
        <div className={cn("min-w-0", collapsed && "lg:hidden")}>
          <p className="truncate text-sm font-semibold leading-tight text-slate-900">
            ProcureFlow
          </p>
          <p className="truncate text-[10px] leading-tight text-slate-500">
            Govt. of Maharashtra
          </p>
        </div>
      </div>

      <div className={cn("border-b border-slate-100 px-4 py-3", collapsed && "lg:hidden")}>
        <p className="text-[10px] font-semibold uppercase tracking-wider text-brand-700">
          {ROLE_LABEL[user.role]}
        </p>
        <p className="mt-0.5 text-[11px] leading-snug text-slate-500">
          {ROLE_TAGLINE[user.role]}
        </p>
      </div>

      <nav className="flex-1 space-y-4 overflow-y-auto px-3 py-4" aria-label="Main">
        {groups.map((group, groupIndex) => (
          <div key={group.label ?? `group-${groupIndex}`} className="space-y-1">
            {group.label && (
              <p
                className={cn(
                  "px-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400",
                  collapsed && "lg:hidden",
                )}
              >
                {group.label}
              </p>
            )}
            {group.items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                title={collapsed ? item.label : item.description}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    collapsed && "lg:justify-center lg:px-0",
                    isActive
                      ? "bg-brand-50 text-brand-800"
                      : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
                  )
                }
              >
                <item.icon className="h-4 w-4 shrink-0" aria-hidden />
                <span className={cn("truncate", collapsed && "lg:hidden")}>{item.label}</span>
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      <div className="border-t border-slate-100 p-3">
        <button
          onClick={() => setCollapsed((value) => !value)}
          className="hidden w-full items-center gap-3 rounded-md px-3 py-2 text-sm text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-800 lg:flex"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? (
            <PanelLeft className="h-4 w-4 shrink-0" aria-hidden />
          ) : (
            <PanelLeftClose className="h-4 w-4 shrink-0" aria-hidden />
          )}
          <span className={cn(collapsed && "lg:hidden")}>Collapse</span>
        </button>
      </div>
    </div>
  )

  return (
    <div className="flex min-h-screen bg-slate-100">
      {/* Off-canvas drawer, below lg. */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-slate-900/40"
            onClick={() => setMobileOpen(false)}
            aria-hidden
          />
          <div className="absolute left-0 top-0 h-full w-64 shadow-xl">
            <button
              onClick={() => setMobileOpen(false)}
              className="absolute right-2 top-3 z-10 rounded-md p-1.5 text-slate-400 hover:bg-slate-100"
              aria-label="Close navigation"
            >
              <X className="h-4 w-4" aria-hidden />
            </button>
            {sidebar}
          </div>
        </div>
      )}

      <aside
        className={cn(
          "hidden shrink-0 border-r border-slate-200 transition-[width] duration-150 lg:block",
          collapsed ? "w-[4.25rem]" : "w-64",
        )}
      >
        <div className="sticky top-0 h-screen">{sidebar}</div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-slate-200 bg-white px-4 sm:px-6">
          <button
            onClick={() => setMobileOpen(true)}
            className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100 lg:hidden"
            aria-label="Open navigation"
          >
            <Menu className="h-5 w-5" aria-hidden />
          </button>

          <div className="flex min-w-0 items-center gap-2 lg:hidden">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-brand-700 text-white">
              <Building2 className="h-4 w-4" aria-hidden />
            </div>
            <span className="truncate text-sm font-semibold text-slate-900">ProcureFlow</span>
          </div>

          <p className="hidden text-sm text-slate-500 lg:block">
            Innovation Procurement Platform
          </p>

          <div className="ml-auto flex items-center gap-1 sm:gap-2">
            <NotificationBell />

            <div className="hidden items-center gap-2.5 border-l border-slate-200 pl-3 sm:flex">
              <div
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold text-slate-600"
                aria-hidden
              >
                {initials(user.fullName)}
              </div>
              <div className="min-w-0 leading-tight">
                <p className="truncate text-sm font-medium text-slate-800">{user.fullName}</p>
                <p className="truncate text-[11px] text-slate-500">{ROLE_LABEL[user.role]}</p>
              </div>
            </div>

            <button
              onClick={logout}
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
              aria-label="Sign out"
              title="Sign out"
            >
              <LogOut className="h-4 w-4" aria-hidden />
            </button>
          </div>
        </header>

        <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-6 sm:px-6 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

function initials(fullName: string): string {
  return fullName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("")
}
