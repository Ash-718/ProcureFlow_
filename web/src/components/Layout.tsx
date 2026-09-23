import { Link, NavLink, Outlet } from 'react-router-dom'

import { useAuth, type Role } from '@/auth/AuthContext'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ThemeToggle } from '@/components/ThemeToggle'
import { cn } from '@/lib/utils'

/** Each screen and the roles allowed to see it. The server enforces the same. */
export const NAV: { to: string; label: string; roles: Role[] }[] = [
  { to: '/government', label: 'Department', roles: ['GOVERNMENT'] },
  { to: '/startup', label: 'My portal', roles: ['STARTUP'] },
  { to: '/evaluation', label: 'Evaluation queue', roles: ['EXPERT'] },
  { to: '/partnerships', label: 'Partnerships', roles: ['GOVERNMENT', 'ADMIN'] },
  { to: '/fairness', label: 'Fairness & governance', roles: ['ADMIN'] },
  { to: '/admin/rules', label: 'Procurement rules', roles: ['ADMIN'] },
]

export function Layout() {
  const { user, logout } = useAuth()
  if (!user) return null

  const visible = NAV.filter((item) => item.roles.includes(user.role))

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b border-border bg-card">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-4 px-6 py-3">
          <Link to="/" className="font-semibold">
            ProcureFlow
          </Link>
          <Badge variant="outline" title="This is a prototype populated with sample data">
            SIH26136 prototype
          </Badge>

          <nav className="flex flex-wrap gap-1">
            {visible.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    'rounded-md px-3 py-1.5 text-sm',
                    isActive ? 'bg-accent font-medium' : 'text-muted-foreground hover:bg-accent',
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-3 text-sm">
            <span className="text-muted-foreground">{user.full_name}</span>
            <Badge variant="secondary">{user.role}</Badge>
            <ThemeToggle />
            <Button size="sm" variant="outline" onClick={logout}>
              Sign out
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-6">
        <Outlet />
      </main>

      <footer className="mx-auto max-w-6xl px-6 pb-10 text-xs text-muted-foreground">
        Sample data throughout. Matching scores are prototype-generated and are not official
        evaluation criteria.
      </footer>
    </div>
  )
}
