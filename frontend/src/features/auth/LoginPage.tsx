import React, { useState } from 'react'
import { useNavigate, Navigate, useLocation } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { api, setAuthToken } from '@/lib/api'
import { supabase } from '@/lib/supabase'
import { useAuth } from '@/context/AuthContext'
import { Lock, Mail, ArrowRight, AlertCircle, Loader2 } from 'lucide-react'
import type { User } from '@/types'

const loginSchema = z.object({
  email: z
    .string()
    .min(1, 'Work email is required')
    .email('Please enter a valid email address'),
  password: z
    .string()
    .min(1, 'Password is required'),
})

type LoginFormValues = z.infer<typeof loginSchema>

export const LoginPage: React.FC = () => {
  const { login, isAuthenticated } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [serverError, setServerError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: '',
      password: '',
    },
  })

  // If already authenticated, redirect to dashboard immediately
  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />
  }

  const onSubmit = async (data: LoginFormValues) => {
    setServerError(null)
    try {
      const { data: authData, error } = await supabase.auth.signInWithPassword({
        email: data.email.trim(),
        password: data.password,
      })

      if (error || !authData.session) {
        setServerError(error?.message || 'Invalid email or password')
        return
      }

      const accessToken = authData.session.access_token
      setAuthToken(accessToken)

      try {
        const meRes = await api.get<User>('/auth/me', {
          headers: { Authorization: `Bearer ${accessToken}` },
        })
        login(accessToken, meRes.data)
        const fromPath = (location.state as { from?: { pathname: string } })?.from?.pathname
        navigate(fromPath || '/dashboard', { replace: true })
      } catch (profileErr: any) {
        await supabase.auth.signOut()
        setAuthToken(null)
        const detail =
          profileErr?.response?.data?.detail ||
          'User account inactive or not provisioned in application directory'
        setServerError(detail)
      }
    } catch (err: unknown) {
      setServerError(
        err instanceof Error ? err.message : 'Authentication failed. Please verify your connection.'
      )
    }
  }

  return (
    <div>
      <div className="mb-6">
        <h3 className="text-lg font-semibold text-white">Sign In to Workspace</h3>
        <p className="mt-1 text-xs text-slate-400">
          Enter your authorized enterprise credentials to access the ledger.
        </p>
      </div>

      {serverError && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-red-800 bg-red-900/30 p-3 text-xs text-red-300 animate-in fade-in">
          <AlertCircle className="h-4 w-4 shrink-0 text-red-400" />
          <span>{serverError}</span>
        </div>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <label className="block text-xs font-medium text-slate-300">
            Work Email Address
          </label>
          <div className="relative mt-1">
            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
              <Mail className="h-4 w-4 text-slate-500" />
            </div>
            <input
              type="email"
              autoComplete="email"
              {...register('email')}
              className={`block w-full rounded-lg border bg-slate-900/80 py-2 pl-9 pr-3 text-sm text-white placeholder-slate-500 focus:outline-hidden ${
                errors.email
                  ? 'border-red-500 focus:border-red-500 focus:ring-1 focus:ring-red-500'
                  : 'border-slate-700 focus:border-sky-500 focus:ring-1 focus:ring-sky-500'
              }`}
              placeholder="user@organization.com"
            />
          </div>
          {errors.email && (
            <p className="mt-1 text-xs text-red-400">{errors.email.message}</p>
          )}
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-300">
            Account Password
          </label>
          <div className="relative mt-1">
            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
              <Lock className="h-4 w-4 text-slate-500" />
            </div>
            <input
              type="password"
              autoComplete="current-password"
              {...register('password')}
              className={`block w-full rounded-lg border bg-slate-900/80 py-2 pl-9 pr-3 text-sm text-white placeholder-slate-500 focus:outline-hidden ${
                errors.password
                  ? 'border-red-500 focus:border-red-500 focus:ring-1 focus:ring-red-500'
                  : 'border-slate-700 focus:border-sky-500 focus:ring-1 focus:ring-sky-500'
              }`}
              placeholder="••••••••"
            />
          </div>
          {errors.password && (
            <p className="mt-1 text-xs text-red-400">{errors.password.message}</p>
          )}
        </div>

        <button
          type="submit"
          disabled={isSubmitting}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-sky-600 px-4 py-2.5 text-sm font-semibold text-white shadow-md hover:bg-sky-500 focus:outline-hidden disabled:opacity-50 transition-colors"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Authenticating...</span>
            </>
          ) : (
            <>
              <span>Sign In</span>
              <ArrowRight className="h-4 w-4" />
            </>
          )}
        </button>
      </form>
    </div>
  )
}

export default LoginPage
