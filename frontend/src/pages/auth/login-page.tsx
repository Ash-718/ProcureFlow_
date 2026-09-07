import { useState } from "react"
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom"
import { Building2, Loader2 } from "lucide-react"
import { useAuth } from "@/hooks/useAuth"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { apiErrorMessage } from "@/api/client"
import { ROLE_HOME } from "@/components/layout/nav-config"

const DEMO_ACCOUNTS = [
  { role: "Government", email: "government@demo.com" },
  { role: "Startup", email: "startup@demo.com" },
  { role: "Expert", email: "expert@demo.com" },
  { role: "Admin", email: "admin@demo.com" },
]

export function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  if (user) {
    const from = (location.state as { from?: Location })?.from?.pathname
    return <Navigate to={from || ROLE_HOME[user.role]} replace />
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const loggedInUser = await login(email, password)
      navigate(ROLE_HOME[loggedInUser.role], { replace: true })
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-md">
        <div className="mb-8 flex flex-col items-center text-center">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-brand-600 text-white">
            <Building2 className="h-6 w-6" />
          </div>
          <h1 className="text-xl font-bold text-slate-900">INNOVATE-GOV</h1>
          <p className="text-sm text-slate-500">AI-powered innovation procurement platform · SIH26136</p>
        </div>

        <form onSubmit={onSubmit} className="space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email" type="email" required autoFocus
              value={email} onChange={(e) => setEmail(e.target.value)}
              placeholder="government@demo.com"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password" type="password" required
              value={password} onChange={(e) => setPassword(e.target.value)}
              placeholder="Demo@123"
            />
          </div>
          {error && <p className="rounded-md bg-danger-50 px-3 py-2 text-sm text-danger-700">{error}</p>}
          <Button type="submit" className="w-full" disabled={loading}>
            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
            Sign in
          </Button>
          <p className="text-center text-sm text-slate-500">
            New startup?{" "}
            <Link to="/register" className="font-medium text-brand-600 hover:underline">
              Register here
            </Link>
          </p>
        </form>

        <div className="mt-6 rounded-xl border border-dashed border-slate-300 bg-white/60 p-4">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Demo accounts</p>
          <div className="grid grid-cols-2 gap-2 text-xs">
            {DEMO_ACCOUNTS.map((acc) => (
              <button
                key={acc.email}
                type="button"
                onClick={() => {
                  setEmail(acc.email)
                  setPassword("Demo@123")
                }}
                className="rounded-md border border-slate-200 px-2 py-1.5 text-left hover:border-brand-300 hover:bg-brand-50"
              >
                <span className="block font-medium text-slate-700">{acc.role}</span>
                <span className="text-slate-400">{acc.email}</span>
              </button>
            ))}
          </div>
          <p className="mt-2 text-[11px] text-slate-400">Password for all demo accounts: Demo@123</p>
        </div>
      </div>
    </div>
  )
}
