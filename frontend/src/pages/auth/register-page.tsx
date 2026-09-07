import { useState } from "react"
import { Link, Navigate, useNavigate } from "react-router-dom"
import { Building2, Loader2 } from "lucide-react"
import { useAuth } from "@/hooks/useAuth"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { apiErrorMessage } from "@/api/client"
import { ROLE_HOME } from "@/components/layout/nav-config"
import type { Role } from "@/types"

export function RegisterPage() {
  const { user, register } = useAuth()
  const navigate = useNavigate()
  const [role, setRole] = useState<Role>("STARTUP")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [fullName, setFullName] = useState("")
  const [orgName, setOrgName] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  if (user) return <Navigate to={ROLE_HOME[user.role]} replace />

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const payload =
        role === "STARTUP"
          ? { email, password, fullName, role, companyName: orgName }
          : { email, password, fullName, role, departmentName: orgName }
      const registeredUser = await register(payload)
      navigate(ROLE_HOME[registeredUser.role], { replace: true })
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-8 flex flex-col items-center text-center">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-brand-600 text-white">
            <Building2 className="h-6 w-6" />
          </div>
          <h1 className="text-xl font-bold text-slate-900">Create an account</h1>
          <p className="text-sm text-slate-500">Startups and government departments can self-register</p>
        </div>

        <form onSubmit={onSubmit} className="space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="space-y-1.5">
            <Label>I am registering as</Label>
            <Select value={role} onValueChange={(v) => setRole(v as Role)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="STARTUP">A Startup</SelectItem>
                <SelectItem value="GOVERNMENT">A Government Department</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="fullName">Your full name</Label>
            <Input id="fullName" required value={fullName} onChange={(e) => setFullName(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="orgName">{role === "STARTUP" ? "Company name" : "Department name"}</Label>
            <Input id="orgName" required value={orgName} onChange={(e) => setOrgName(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password" type="password" required minLength={8}
              value={password} onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          {error && <p className="rounded-md bg-danger-50 px-3 py-2 text-sm text-danger-700">{error}</p>}
          <Button type="submit" className="w-full" disabled={loading}>
            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
            Create account
          </Button>
          <p className="text-center text-sm text-slate-500">
            Already have an account?{" "}
            <Link to="/login" className="font-medium text-brand-600 hover:underline">
              Sign in
            </Link>
          </p>
        </form>
      </div>
    </div>
  )
}
