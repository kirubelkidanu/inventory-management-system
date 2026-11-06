import React from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'

export const ProtectedRoute: React.FC = () => {
  const { user, isAuthenticated, isLoading } = useAuth()
  const location = useLocation()

  // Only render the full-screen spinner on initial cold boot when loading AND user is null
  if (isLoading && !user) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-slate-900">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-sky-400 border-t-transparent" />
          <p className="text-sm font-medium text-slate-300">Initializing system...</p>
        </div>
      </div>
    )
  }

  // If initial load finished and there is no authenticated user, redirect cleanly to login
  if (!isAuthenticated && !user) {
    // Preserve attempted location so user can be redirected after login
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  // Once user profile is loaded, keep rendering Outlet seamlessly without unmounting
  return <Outlet />
}

export default ProtectedRoute
