import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL || '/api/v1'

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 120000,
})

// Request Interceptor: Attach JWT Bearer Token
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('access_token')
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
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
      console.error("API 401 Unauthorized:", error.config?.url)
      const isAuthEndpoint =
        error.config?.url?.includes('/auth/token') ||
        error.config?.url?.includes('/auth/demo-login')
      // Clear token on 401 unauthorized only when navigating protected routes
      if (typeof window !== 'undefined' && window.location.pathname !== '/login' && !isAuthEndpoint) {
        localStorage.removeItem('access_token')
        localStorage.removeItem('auth_user')
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default api
