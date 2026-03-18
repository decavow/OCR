import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'

export default function AdminRoute() {
  const { user, loading } = useAuth()

  if (loading) {
    return null
  }

  if (!user?.is_admin) {
    return <Navigate to="/dashboard" replace />
  }

  return <Outlet />
}
