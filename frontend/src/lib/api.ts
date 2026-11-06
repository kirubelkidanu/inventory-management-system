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

export const setAuthToken = (token: string | null) => {
  if (token) {
    api.defaults.headers.common['Authorization'] = `Bearer ${token}`
    if (typeof window !== 'undefined') {
      localStorage.setItem('access_token', token)
    }
  } else {
    delete api.defaults.headers.common['Authorization']
    if (typeof window !== 'undefined') {
      localStorage.removeItem('access_token')
    }
  }
}

// Attach token on initialization if present in localStorage
if (typeof window !== 'undefined') {
  const existingToken = localStorage.getItem('access_token')
  if (existingToken) {
    api.defaults.headers.common['Authorization'] = `Bearer ${existingToken}`
  }
}

// Request Interceptor: Synchronously attach JWT Bearer Token if absent and sanitize URLs
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    if (!config.headers.Authorization && typeof window !== 'undefined') {
      const token = localStorage.getItem('access_token')
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

// Response Interceptor: Error normalization and protected route 401 handling
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      const url = error.config?.url || ''
      const isAuthEndpoint = url.includes('/auth/me') || url.includes('/auth/token')
      const isLoginPage = typeof window !== 'undefined' && window.location.pathname === '/login'

      // Only redirect on confirmed 401 when on a protected route and not during auth calls
      if (typeof window !== 'undefined' && !isLoginPage && !isAuthEndpoint) {
        localStorage.removeItem('access_token')
        localStorage.removeItem('auth_user')
        delete api.defaults.headers.common['Authorization']
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default api
