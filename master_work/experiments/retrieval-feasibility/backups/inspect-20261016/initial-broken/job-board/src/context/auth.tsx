import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { api } from '#/lib/api'

interface User {
  _id: string
  name: string
  email: string
  role: 'employer' | 'candidate'
  companyName?: string
  headline?: string
  skills?: string[]
  location?: string
  bio?: string
  resumeUrl?: string
  companyWebsite?: string
  companyDescription?: string
  industry?: string
  companySize?: string
}

interface AuthCtx {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (data: object) => Promise<void>
  logout: () => void
  updateUser: (data: object) => Promise<void>
}

const Ctx = createContext<AuthCtx | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('jb_token')
    if (!token) { setLoading(false); return }
    api.me()
      .then((d: any) => setUser(d.user))
      .catch(() => localStorage.removeItem('jb_token'))
      .finally(() => setLoading(false))
  }, [])

  async function login(email: string, password: string) {
    const d: any = await api.login({ email, password })
    localStorage.setItem('jb_token', d.token)
    setUser(d.user)
  }

  async function register(data: object) {
    const d: any = await api.register(data)
    localStorage.setItem('jb_token', d.token)
    setUser(d.user)
  }

  function logout() {
    localStorage.removeItem('jb_token')
    setUser(null)
  }

  async function updateUser(data: object) {
    const d: any = await api.updateProfile(data)
    setUser(d.user)
  }

  return <Ctx.Provider value={{ user, loading, login, register, logout, updateUser }}>{children}</Ctx.Provider>
}

export function useAuth() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
