import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'

const rawBaseUrl =
  import.meta.env.VITE_API_URL ||
  import.meta.env.VITE_API_BASE_URL ||
  'https://api-inventory.moderngebeya.com/api/v1'
const API_BASE_URL = rawBaseUrl.replace(/\/+$/, '')

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 120000,
})

export function getStoredToken(): string | null {
  if (typeof window === 'undefined') return null

  // 1. Explicit application token keys
  const token = localStorage.getItem('ims_token') || localStorage.getItem('access_token')
  if (token) return token

  // 2. Supabase auth token session key in localStorage (e.g. sb-*-auth-token)
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)
      if (key && key.startsWith('sb-') && key.endsWith('-auth-token')) {
        const item = localStorage.getItem(key)
        if (item) {
          const parsed = JSON.parse(item)
          const sbToken = parsed?.access_token || parsed?.currentSession?.access_token
          if (sbToken && typeof sbToken === 'string') {
            return sbToken
          }
        }
      }
    }
  } catch {
    // Ignore JSON parse errors
  }

  return null
}

export const setAuthToken = (token: string | null) => {
  if (token) {
    api.defaults.headers.common['Authorization'] = `Bearer ${token}`
    if (typeof window !== 'undefined') {
      localStorage.setItem('ims_token', token)
      localStorage.setItem('access_token', token)
    }
  } else {
    delete api.defaults.headers.common['Authorization']
    if (typeof window !== 'undefined') {
      localStorage.removeItem('ims_token')
      localStorage.removeItem('access_token')
    }
  }
}

// Attach token on initialization if present in localStorage
if (typeof window !== 'undefined') {
  const existingToken = getStoredToken()
  if (existingToken) {
    api.defaults.headers.common['Authorization'] = `Bearer ${existingToken}`
  }
}

// Request Interceptor: Synchronously attach JWT Bearer Token if absent and sanitize URLs
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    if (!config.headers.Authorization && typeof window !== 'undefined') {
      const token = getStoredToken()
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
    }
    if (config.url) {
      // Prevent unintended double slashes (e.g. //opening-balance -> /opening-balance)
      config.url = config.url.replace(/^\/\/+/, '/')
    }
    return config
  },
  (error: AxiosError) => {
    return Promise.reject(error)
  }
)

// Response Interceptor: Safe error propagation without hard window.location reloads
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    // CRITICAL: A transient 401 or network error on a background query must NEVER
    // nuke localStorage or trigger a hard window.location browser reload!
    // Auth state lifecycle is strictly owned and managed by AuthContext.
    return Promise.reject(error)
  }
)

export default api
