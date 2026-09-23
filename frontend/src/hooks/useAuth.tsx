import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react"
import { AuthApi } from "@/api/endpoints"
import { TOKEN_STORAGE_KEY } from "@/api/client"
import type { CurrentUser, Role } from "@/types"

interface AuthContextValue {
  user: CurrentUser | null
  loading: boolean
  login: (email: string, password: string) => Promise<CurrentUser>
  register: (payload: {
    email: string; password: string; fullName: string; role: Role
    companyName?: string; departmentName?: string; ministry?: string; region?: string
  }) => Promise<CurrentUser>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem(TOKEN_STORAGE_KEY)
    if (!token) {
      setLoading(false)
      return
    }
    AuthApi.me()
      .then(setUser)
      .catch(() => localStorage.removeItem(TOKEN_STORAGE_KEY))
      .finally(() => setLoading(false))
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const response = await AuthApi.login(email, password)
    localStorage.setItem(TOKEN_STORAGE_KEY, response.token)
    const currentUser: CurrentUser = {
      id: response.userId, email: response.email, fullName: response.fullName, role: response.role,
    }
    setUser(currentUser)
    return currentUser
  }, [])

  const register = useCallback(async (payload: Parameters<AuthContextValue["register"]>[0]) => {
    const response = await AuthApi.register(payload)
    localStorage.setItem(TOKEN_STORAGE_KEY, response.token)
    const currentUser: CurrentUser = {
      id: response.userId, email: response.email, fullName: response.fullName, role: response.role,
    }
    setUser(currentUser)
    return currentUser
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_STORAGE_KEY)
    setUser(null)
  }, [])

  const value = useMemo(() => ({ user, loading, login, register, logout }), [user, loading, login, register, logout])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth must be used within AuthProvider")
  return ctx
}
