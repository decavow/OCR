// Top nav: logo, Dashboard/Batches/Settings links, user avatar

import { Link } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'

export default function AppHeader() {
  const { user, logout } = useAuth()

  const handleLogout = async () => {
    await logout()
  }

  return (
    <header className="app-header">
      <div className="logo">
        <Link to="/">OCR Platform</Link>
      </div>
      <nav>
        <Link to="/dashboard">Dashboard</Link>
        <Link to="/batches">Batches</Link>
        <Link to="/upload">Upload</Link>
      </nav>
      <div className="user-menu">
        <span>{user?.email}</span>
        <button onClick={handleLogout}>Logout</button>
      </div>
    </header>
  )
}
