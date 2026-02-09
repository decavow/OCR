// Sidebar navigation

import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'

export default function Sidebar() {
  const location = useLocation()
  const { user, logout } = useAuth()

  const isActive = (path: string) => location.pathname === path

  const handleLogout = async () => {
    await logout()
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <Link to="/">OCR Platform</Link>
      </div>

      <nav className="sidebar-nav">
        <Link to="/dashboard" className={isActive('/dashboard') || isActive('/') ? 'active' : ''}>
          Dashboard
        </Link>
        <Link to="/upload" className={isActive('/upload') ? 'active' : ''}>
          Upload
        </Link>
        <Link to="/batches" className={location.pathname.startsWith('/batches') ? 'active' : ''}>
          Batches
        </Link>
      </nav>

      <div className="sidebar-footer">
        <div className="user-info">
          <span>{user?.email}</span>
          <button onClick={handleLogout}>Logout</button>
        </div>
      </div>
    </aside>
  )
}
