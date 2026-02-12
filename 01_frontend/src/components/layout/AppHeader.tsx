import { Link } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import { Button as ShadcnButton } from '@/components/ui/button'

export default function AppHeader() {
  const { user, logout } = useAuth()

  return (
    <header className="flex items-center justify-between h-14 px-6 border-b border-border bg-card">
      <div className="font-semibold text-foreground">
        <Link to="/">OCR Platform</Link>
      </div>
      <nav className="flex items-center gap-4">
        <Link to="/dashboard" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Dashboard</Link>
        <Link to="/batches" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Batches</Link>
        <Link to="/upload" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Upload</Link>
      </nav>
      <div className="flex items-center gap-3">
        <span className="text-sm text-muted-foreground">{user?.email}</span>
        <ShadcnButton variant="ghost" size="sm" onClick={() => logout()}>
          Logout
        </ShadcnButton>
      </div>
    </header>
  )
}
