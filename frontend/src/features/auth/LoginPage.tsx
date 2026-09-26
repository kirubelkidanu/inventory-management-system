import React, { useState } from 'react'
import { useNavigate, Navigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import axios from 'axios'
import { api } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { Lock, Mail, ArrowRight, AlertCircle, ShieldCheck } from 'lucide-react'
import type { UserRole } from '@/types'

const loginSchema = z.object({
  email: z
    .string()
    .min(1, 'Work email is required')
    .email('Please enter a valid email address'),
  password: z
    .string()
    .min(6, 'Password must be at least 6 characters'),
})

type LoginFormValues = z.infer<typeof loginSchema>

interface DemoRoleConfig {
  role: UserRole
  name: string
  email: string
  label: string
  badgeStyle: string
}

const DEMO_ROLES: DemoRoleConfig[] = [
  {
    role: 'ADMIN',
    name: 'Alice Administrator',
    email: 'admin@ims.local',
    label: 'Admin',
    badgeStyle: 'border-purple-800/40 bg-purple-950/40 text-purple-300 hover:bg-purple-900/50',
  },
  {
    role: 'INVENTORY_MANAGER',
    name: 'Bob Manager',
    email: 'manager@ims.local',
    label: 'Inv. Manager',
    badgeStyle: 'border-sky-800/40 bg-sky-950/40 text-sky-300 hover:bg-sky-900/50',
  },
  {
    role: 'STORE_KEEPER',
    name: 'Charlie Keeper',
    email: 'storekeeper@ims.local',
    label: 'Store Keeper',
    badgeStyle: 'border-amber-800/40 bg-amber-950/40 text-amber-300 hover:bg-amber-900/50',
  },
  {
    role: 'VIEWER',
    name: 'Diana Auditor',
    email: 'viewer@ims.local',
    label: 'Viewer',
    badgeStyle: 'border-slate-700 bg-slate-800 text-slate-300 hover:bg-slate-700',
  },
]

export const LoginPage: React.FC = () => {
  const { login, isAuthenticated } = useAuth()
  const navigate = useNavigate()
  const [serverError, setServerError] = useState<string | null>(null)
  const [quickLoadingRole, setQuickLoadingRole] = useState<UserRole | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: 'admin@ims.local',
      password: 'password123',
    },
  })

  // If already authenticated, redirect to dashboard immediately
  if (isAuthenticated) {
    return <Navigate to="/" replace />
  }

  const onSubmit = async (data: LoginFormValues) => {
    setServerError(null)
    try {
      const response = await api.post<{
        access_token: string
        token_type: string
        user: {
          id: string
          email: string
          full_name: string
          role: UserRole
          is_active: boolean
        }
      }>('/auth/token', {
        email: data.email,
        password: data.password,
      })

      const { access_token, user } = response.data
      login(access_token, user)
      navigate('/', { replace: true })
    } catch (err: unknown) {
      if (axios.isAxiosError(err) && err.response?.data?.detail) {
        setServerError(String(err.response.data.detail))
      } else {
        setServerError(
          err instanceof Error ? err.message : 'Invalid credentials provided'
        )
      }
    }
  }

  const handleQuickRoleLogin = async (config: DemoRoleConfig) => {
    setServerError(null)
    setQuickLoadingRole(config.role)
    try {
      const response = await api.post<{
        access_token: string
        token_type: string
        user: {
          id: string
          email: string
          full_name: string
          role: UserRole
          is_active: boolean
        }
      }>('/auth/demo-login', {
        role: config.role,
      })

      const { access_token, user } = response.data
      login(access_token, user)
      navigate('/', { replace: true })
    } catch (err: unknown) {
      if (axios.isAxiosError(err) && err.response?.data?.detail) {
        setServerError(String(err.response.data.detail))
      } else {
        setServerError('Quick demo sign-in failed. Please verify the backend server is running.')
      }
    } finally {
      setQuickLoadingRole(null)
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
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-red-800 bg-red-900/30 p-3 text-xs text-red-300">
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
          <span>{isSubmitting ? 'Authenticating...' : 'Sign In'}</span>
          <ArrowRight className="h-4 w-4" />
        </button>
      </form>

      {/* Instant Demo Role Switcher */}
      <div className="mt-8 border-t border-slate-700/80 pt-6">
        <div className="flex items-center justify-between">
          <p className="text-xs font-medium text-slate-400">
            Instant Demo Sign-In
          </p>
          <div className="flex items-center gap-1 text-[10px] text-slate-500">
            <ShieldCheck className="h-3 w-3 text-emerald-500" />
            <span>RBAC Testing</span>
          </div>
        </div>
        <p className="mt-1 text-[11px] text-slate-500">
          Switch roles immediately to test role-based access control and voucher permissions:
        </p>
        <div className="mt-3 grid grid-cols-2 gap-2">
          {DEMO_ROLES.map((cfg) => (
            <button
              key={cfg.role}
              type="button"
              disabled={quickLoadingRole !== null || isSubmitting}
              onClick={() => handleQuickRoleLogin(cfg)}
              className={`flex items-center justify-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors disabled:opacity-50 ${cfg.badgeStyle}`}
            >
              {quickLoadingRole === cfg.role && (
                <div className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
              )}
              <span>{cfg.label}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

export default LoginPage
