import React, { createContext, useContext, useState, useEffect, useMemo, useRef } from 'react'
import type { User, UserRole } from '@/types'
import { supabase } from '@/lib/supabase'
import { api, setAuthToken } from '@/lib/api'

interface AuthContextType {
  user: User | null
  token: string | null
  isLoading: boolean
  isInitialized: boolean
  isAuthenticated: boolean
  login: (token: string, user: User) => void
  logout: () => Promise<void>
  hasRole: (...roles: UserRole[]) => boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // Synchronously seed initial state from localStorage if available
  const [token, setToken] = useState<string | null>(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('access_token')
    }
    return null
  })

  const [user, setUser] = useState<User | null>(() => {
    if (typeof window !== 'undefined') {
      try {
        const stored = localStorage.getItem('auth_user')
        return stored ? JSON.parse(stored) : null
      } catch {
        return null
      }
    }
    return null
  })

  // isLoading starts true on initial mount and permanently transitions to false
  const [isLoading, setIsLoading] = useState<boolean>(true)
  const [isInitialized, setIsInitialized] = useState<boolean>(false)

  // Refs for deduplication and race-prevention
  const lastFetchedTokenRef = useRef<string | null>(token)
  const isFetchingRef = useRef<boolean>(false)
  const currentUserRef = useRef<User | null>(user)

  // Keep currentUserRef synchronized with state
  useEffect(() => {
    currentUserRef.current = user
  }, [user])

  // Profile fetcher with token deduplication and error isolation
  const fetchUserProfile = async (accessToken: string, force = false): Promise<User | null> => {
    if (!accessToken) return null

    // Deduplicate if already fetched for this exact token and user profile is present
    if (!force && lastFetchedTokenRef.current === accessToken && currentUserRef.current) {
      return currentUserRef.current
    }

    if (isFetchingRef.current) {
      return currentUserRef.current
    }

    isFetchingRef.current = true
    try {
      setAuthToken(accessToken)
      const res = await api.get<User>('/auth/me', {
        headers: { Authorization: `Bearer ${accessToken}` },
      })
      const profile = res.data
      lastFetchedTokenRef.current = accessToken
      currentUserRef.current = profile
      setUser(profile)
      setToken(accessToken)
      if (typeof window !== 'undefined') {
        localStorage.setItem('auth_user', JSON.stringify(profile))
        localStorage.setItem('access_token', accessToken)
      }
      return profile
    } catch (err: any) {
      console.warn('[AuthContext] Profile fetch error:', err)
      const status = err?.response?.status
      // Only clear user on confirmed 401 unauthorized or when no profile was ever loaded
      if (status === 401 || !currentUserRef.current) {
        lastFetchedTokenRef.current = null
        currentUserRef.current = null
        setUser(null)
        setToken(null)
        setAuthToken(null)
        if (typeof window !== 'undefined') {
          localStorage.removeItem('auth_user')
          localStorage.removeItem('access_token')
        }
      }
      return null
    } finally {
      isFetchingRef.current = false
    }
  }

  useEffect(() => {
    let isMounted = true

    const initializeAuth = async () => {
      try {
        const { data: { session } } = await supabase.auth.getSession()
        if (session?.access_token) {
          await fetchUserProfile(session.access_token)
        } else {
          // No active Supabase session
          if (isMounted) {
            lastFetchedTokenRef.current = null
            currentUserRef.current = null
            setToken(null)
            setUser(null)
            setAuthToken(null)
            if (typeof window !== 'undefined') {
              localStorage.removeItem('auth_user')
              localStorage.removeItem('access_token')
            }
          }
        }
      } catch (err) {
        console.warn('[AuthContext] Error during auth initialization:', err)
      } finally {
        if (isMounted) {
          setIsLoading(false)
          setIsInitialized(true)
        }
      }
    }

    initializeAuth()

    const { data: { subscription } } = supabase.auth.onAuthStateChange(async (event, session) => {
      try {
        if (event === 'SIGNED_OUT' || (!session && event !== 'INITIAL_SESSION')) {
          if (isMounted) {
            lastFetchedTokenRef.current = null
            currentUserRef.current = null
            setToken(null)
            setUser(null)
            setAuthToken(null)
            if (typeof window !== 'undefined') {
              localStorage.removeItem('auth_user')
              localStorage.removeItem('access_token')
            }
          }
          return
        }

        if (session?.access_token) {
          const accessToken = session.access_token

          if (event === 'TOKEN_REFRESHED') {
            // Silently update token without setting isLoading = true or clearing user
            setAuthToken(accessToken)
            setToken(accessToken)
            lastFetchedTokenRef.current = accessToken
            if (typeof window !== 'undefined') {
              localStorage.setItem('access_token', accessToken)
            }
            return
          }

          if (event === 'SIGNED_IN') {
            // If login() already populated user for this token, skip duplicate fetch
            if (lastFetchedTokenRef.current === accessToken && currentUserRef.current) {
              setAuthToken(accessToken)
              setToken(accessToken)
              return
            }
            // Background fetch without setting isLoading = true
            await fetchUserProfile(accessToken)
            return
          }

          if (event === 'USER_UPDATED') {
            await fetchUserProfile(accessToken, true)
            return
          }

          // Any other session update event
          if (!currentUserRef.current || lastFetchedTokenRef.current !== accessToken) {
            await fetchUserProfile(accessToken)
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
  }, []) // Empty dependency array ensures exactly one subscription on mount

  const login = (newToken: string, newUser: User) => {
    lastFetchedTokenRef.current = newToken
    currentUserRef.current = newUser
    setToken(newToken)
    setUser(newUser)
    setAuthToken(newToken)
    setIsLoading(false)
    setIsInitialized(true)
    if (typeof window !== 'undefined') {
      localStorage.setItem('access_token', newToken)
      localStorage.setItem('auth_user', JSON.stringify(newUser))
    }
  }

  const logout = async () => {
    try {
      await supabase.auth.signOut()
    } catch (e) {
      console.warn('[AuthContext] Error during signOut:', e)
    } finally {
      lastFetchedTokenRef.current = null
      currentUserRef.current = null
      setAuthToken(null)
      localStorage.removeItem('auth_user')
      localStorage.removeItem('access_token')
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
      isInitialized,
      isAuthenticated: !!token && !!user,
      login,
      logout,
      hasRole,
    }),
    [user, token, isLoading, isInitialized]
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
