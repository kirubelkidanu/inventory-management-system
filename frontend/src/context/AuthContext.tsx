import React, { createContext, useContext, useState, useEffect, useMemo } from 'react'
import type { User, UserRole } from '@/types'
import { supabase } from '@/lib/supabase'
import { api, setAuthToken } from '@/lib/api'

interface AuthContextType {
  user: User | null
  token: string | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (token: string, user: User) => void
  logout: () => Promise<void>
  hasRole: (...roles: UserRole[]) => boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(true)

  useEffect(() => {
    let isMounted = true

    const initializeAuth = async () => {
      try {
        const { data: { session } } = await supabase.auth.getSession()
        if (session?.access_token) {
          const accessToken = session.access_token
          setAuthToken(accessToken)

          try {
            const meRes = await api.get<User>('/auth/me', {
              headers: { Authorization: `Bearer ${accessToken}` },
            })
            if (isMounted) {
              setToken(accessToken)
              setUser(meRes.data)
              localStorage.setItem('auth_user', JSON.stringify(meRes.data))
            }
          } catch (profileErr) {
            console.warn('[AuthContext] Failed to resolve active profile:', profileErr)
            if (isMounted) {
              setAuthToken(null)
              localStorage.removeItem('auth_user')
              setToken(null)
              setUser(null)
            }
          }
        } else {
          setAuthToken(null)
          localStorage.removeItem('auth_user')
          if (isMounted) {
            setToken(null)
            setUser(null)
          }
        }
      } catch (err) {
        console.warn('[AuthContext] Error during auth initialization:', err)
      } finally {
        if (isMounted) {
          setIsLoading(false)
        }
      }
    }

    initializeAuth()

    const { data: { subscription } } = supabase.auth.onAuthStateChange(async (event, session) => {
      try {
        if (session?.access_token) {
          const accessToken = session.access_token
          setAuthToken(accessToken)
          try {
            const meRes = await api.get<User>('/auth/me', {
              headers: { Authorization: `Bearer ${accessToken}` },
            })
            if (isMounted) {
              setToken(accessToken)
              setUser(meRes.data)
              localStorage.setItem('auth_user', JSON.stringify(meRes.data))
            }
          } catch (profileErr) {
            console.warn('[AuthContext] State change profile fetch failed:', profileErr)
            if (isMounted) {
              setAuthToken(null)
              localStorage.removeItem('auth_user')
              setToken(null)
              setUser(null)
            }
          }
        } else if (event === 'SIGNED_OUT' || !session) {
          if (isMounted) {
            setAuthToken(null)
            localStorage.removeItem('auth_user')
            setToken(null)
            setUser(null)
          }
        }
      } catch (authChangeErr) {
        console.warn('[AuthContext] Unexpected auth state change error:', authChangeErr)
      }
    })

    return () => {
      isMounted = false
      subscription.unsubscribe()
    }
  }, [])

  const login = (newToken: string, newUser: User) => {
    setToken(newToken)
    setUser(newUser)
    setAuthToken(newToken)
    localStorage.setItem('auth_user', JSON.stringify(newUser))
  }

  const logout = async () => {
    try {
      await supabase.auth.signOut()
    } catch (e) {
      console.warn('[AuthContext] Error during signOut:', e)
    } finally {
      setAuthToken(null)
      localStorage.removeItem('auth_user')
      setToken(null)
      setUser(null)
      if (typeof window !== 'undefined') {
        window.location.href = '/login'
      }
    }
  }

  const hasRole = (...roles: UserRole[]): boolean => {
    if (!user) return false
    return roles.includes(user.role)
  }

  const value = useMemo(
    () => ({
      user,
      token,
      isLoading,
      isAuthenticated: !!token && !!user,
      login,
      logout,
      hasRole,
    }),
    [user, token, isLoading]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

export default AuthContext
