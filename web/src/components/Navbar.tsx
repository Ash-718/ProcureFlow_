import { Link } from 'react-router-dom'
import { useAuth } from '@/auth/AuthContext'
import { Button } from '@/components/ui/button'
import { ThemeToggle } from '@/components/ThemeToggle'

export function Navbar() {
  const { user, logout } = useAuth()

  return (
    <header className="sticky top-0 z-40 w-full border-b border-border bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/75 transition-colors duration-200">
      <div className="mx-auto flex h-16 max-w-4xl items-center justify-between px-4 sm:px-8">
        <div className="flex items-center gap-3">
          <Link to="/" className="flex items-center gap-2 font-bold text-xl text-primary hover:opacity-90">
            <span className="text-primary font-extrabold tracking-tight">ProcureFlow</span>
          </Link>
        </div>

        <div className="flex items-center gap-3">
          {user && (
            <div className="hidden sm:flex items-center gap-2 text-sm text-muted-foreground mr-1">
              <span className="font-medium text-foreground">{user.full_name}</span>
              {user.role && (
                <span className="inline-flex items-center rounded-md bg-secondary px-2 py-0.5 text-xs font-medium text-secondary-foreground border border-border">
                  {user.role}
                </span>
              )}
            </div>
          )}

          <ThemeToggle />

          {user && (
            <Button variant="outline" size="sm" onClick={logout} className="ml-1">
              Sign out
            </Button>
          )}
        </div>
      </div>
    </header>
  )
}
