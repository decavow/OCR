import { useState, useEffect, useCallback } from 'react'
import { Users, FileText, RefreshCw, Shield } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Button as ShadcnButton } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { cn } from '@/lib/utils'
import Loading from '../components/common/Loading'
import { getAdminUsers, getAdminStats, AdminUserItem, AdminStats } from '../api/admin'

export default function AdminUsersPage() {
  const [users, setUsers] = useState<AdminUserItem[]>([])
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const fetchData = useCallback(async () => {
    try {
      const [usersRes, statsRes] = await Promise.all([
        getAdminUsers(),
        getAdminStats(),
      ])
      setUsers(usersRes.items)
      setStats(statsRes)
    } catch {
      // Silently handle errors
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const handleRefresh = () => {
    setRefreshing(true)
    fetchData()
  }

  if (loading) return <Loading text="Loading users..." />

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-foreground">User Management</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Manage platform users and monitor activity.
          </p>
        </div>
        <ShadcnButton onClick={handleRefresh} disabled={refreshing} variant="secondary">
          <RefreshCw className={cn('h-4 w-4 mr-2', refreshing && 'animate-spin')} />
          Refresh
        </ShadcnButton>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <Card>
          <CardContent className="py-4 px-5">
            <div className="flex items-center justify-between mb-3">
              <div className="p-2 rounded-lg bg-primary/10">
                <Users className="h-5 w-5 text-primary" />
              </div>
            </div>
            <div className="text-sm text-muted-foreground">Total Active Users</div>
            <div className="text-2xl font-bold text-foreground mt-1">
              {stats?.total_users ?? 0}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-4 px-5">
            <div className="flex items-center justify-between mb-3">
              <div className="p-2 rounded-lg bg-info/10">
                <FileText className="h-5 w-5 text-info" />
              </div>
            </div>
            <div className="text-sm text-muted-foreground">Total Requests</div>
            <div className="text-2xl font-bold text-foreground mt-1">
              {stats?.total_requests ?? 0}
            </div>
          </CardContent>
        </Card>

      </div>

      {/* User Table */}
      <Card>
        <CardContent className="pt-6">
          <h3 className="text-base font-semibold text-foreground mb-4">All Users</h3>
          {users.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">No users found.</div>
          ) : (
            <div className="rounded-md border border-border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>User</TableHead>
                    <TableHead>Role</TableHead>
                    <TableHead>Requests</TableHead>
                    <TableHead>Created At</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {users.map((u) => (
                    <TableRow key={u.id}>
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <div className="h-9 w-9 rounded-full bg-muted flex items-center justify-center text-sm font-bold text-muted-foreground">
                            {u.email.charAt(0).toUpperCase()}
                          </div>
                          <div>
                            <div className="text-sm font-medium text-foreground">{u.email}</div>
                            <div className="text-xs text-muted-foreground font-mono">{u.id.slice(0, 8)}...</div>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        {u.is_admin ? (
                          <span className="inline-flex items-center rounded-full bg-primary/20 text-primary px-2.5 py-0.5 text-xs font-medium">
                            Admin
                          </span>
                        ) : (
                          <span className="inline-flex items-center rounded-full bg-muted text-muted-foreground px-2.5 py-0.5 text-xs font-medium">
                            User
                          </span>
                        )}
                      </TableCell>
                      <TableCell>
                        <span className="text-sm font-medium text-foreground">
                          {u.total_requests}
                        </span>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {new Date(u.created_at).toLocaleDateString()}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
