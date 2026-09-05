import React from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '../../stores/useAuthStore'

interface ProtectedRouteProps {
  children?: React.ReactNode
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { user, token, isLoadingSession } = useAuthStore()
  const location = useLocation()

  if (isLoadingSession) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-nb">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 rounded-full border-2 border-np border-t-transparent animate-spin" />
          <span className="font-mono text-11 text-nt3 uppercase tracking-wider">Verifying session...</span>
        </div>
      </div>
    )
  }

  if (!token || !user) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return children ? <>{children}</> : null
}
