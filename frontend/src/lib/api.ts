import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'

const rawBaseUrl = import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL || '/api/v1'
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
    localStorage.setItem('access_token', token)
  } else {
    delete api.defaults.headers.common['Authorization']
    localStorage.removeItem('access_token')
  }
}

// Attach token on initialization if present
if (typeof window !== 'undefined') {
  const existingToken = localStorage.getItem('access_token')
  if (existingToken) {
    api.defaults.headers.common['Authorization'] = `Bearer ${existingToken}`
  }
}

// Request Interceptor: Attach JWT Bearer Token and sanitize URLs to avoid double slashes
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('access_token')
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
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

// Response Interceptor: Error normalization and 401 handling
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      const isAuthEndpoint =
        error.config?.url?.includes('/auth/me') ||
        error.config?.url?.includes('/auth/token')
      // Clear token on 401 unauthorized only when navigating protected routes
      if (typeof window !== 'undefined' && window.location.pathname !== '/login' && !isAuthEndpoint) {
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
