import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import { cn } from '@/lib/utils'
import { Separator } from '@/components/ui/separator'
import { Button as ShadcnButton } from '@/components/ui/button'

export default function Sidebar() {
  const location = useLocation()
  const { user, logout } = useAuth()

  const isActive = (path: string) => location.pathname === path

  const linkClass = (active: boolean) =>
    cn(
      'flex items-center gap-2 px-4 py-2 text-sm rounded-md transition-colors',
      active
        ? 'bg-muted text-foreground'
        : 'text-muted-foreground hover:bg-muted hover:text-foreground'
    )

  return (
    <aside className="w-[240px] bg-card border-r border-border flex flex-col fixed h-screen left-0 top-0">
      <div className="px-5 py-5 border-b border-border">
        <Link to="/" className="text-lg font-semibold text-foreground">
          OCR Platform
        </Link>
      </div>

      <nav className="flex-1 flex flex-col gap-1 p-3">
        {!user?.is_admin && (
          <>
            <Link to="/dashboard" className={linkClass(isActive('/dashboard') || isActive('/'))}>
              Dashboard
            </Link>
            <Link to="/upload" className={linkClass(isActive('/upload'))}>
              Upload
            </Link>
            <Link to="/batches" className={linkClass(location.pathname.startsWith('/batches'))}>
              Batches
            </Link>
          </>
        )}

        {user?.is_admin && (
          <>
            <Separator className="my-3" />
            <span className="px-4 text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">
              Admin
            </span>
            <Link
              to="/admin/dashboard"
              className={linkClass(isActive('/admin/dashboard'))}
            >
              Overview
            </Link>
            <Link
              to="/admin/services"
              className={linkClass(location.pathname.startsWith('/admin/services'))}
            >
              Service Management
            </Link>
            <Link
              to="/admin/users"
              className={linkClass(isActive('/admin/users'))}
            >
              User Management
            </Link>
            <Link
              to="/admin/system"
              className={linkClass(isActive('/admin/system'))}
            >
              System Health
            </Link>
          </>
        )}
      </nav>

      <div className="border-t border-border p-4">
        <div className="flex items-center justify-between">
          <div className="flex flex-col min-w-0">
            <span className="text-sm text-foreground truncate">{user?.email}</span>
            {user?.is_admin && (
              <span className="text-xs text-primary font-medium">Admin</span>
            )}
          </div>
          <ShadcnButton variant="ghost" size="sm" onClick={() => logout()}>
            Logout
          </ShadcnButton>
        </div>
      </div>
    </aside>
  )
}
