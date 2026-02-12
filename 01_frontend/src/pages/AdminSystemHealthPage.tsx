import { useState, useEffect, useCallback } from 'react'
import { Server, Zap, AlertOctagon, Activity, RefreshCw } from 'lucide-react'
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
import {
  getAdminStats,
  getAdminServiceInstances,
  getServiceTypes,
  AdminStats,
  AdminServiceInstance,
  ServiceType,
} from '../api/admin'

const instanceStatusStyles: Record<string, string> = {
  ACTIVE: 'bg-success/20 text-success',
  PROCESSING: 'bg-processing/20 text-processing',
  WAITING: 'bg-warning/20 text-warning',
  DRAINING: 'bg-muted text-muted-foreground',
  DEAD: 'bg-destructive/20 text-destructive',
}

export default function AdminSystemHealthPage() {
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [instances, setInstances] = useState<AdminServiceInstance[]>([])
  const [serviceTypes, setServiceTypes] = useState<ServiceType[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const fetchData = useCallback(async () => {
    try {
      const [statsRes, instRes, svcRes] = await Promise.all([
        getAdminStats(),
        getAdminServiceInstances(),
        getServiceTypes(),
      ])
      setStats(statsRes)
      setInstances(instRes.items)
      setServiceTypes(svcRes.items)
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

  if (loading) return <Loading text="Loading system health..." />

  const activeInstances = instances.filter(
    (i) => i.status === 'ACTIVE' || i.status === 'PROCESSING',
  )
  const pendingServiceTypes = serviceTypes.filter((s) => s.status === 'PENDING')
  const totalJobs = stats?.total_jobs ?? 0
  const errorRate =
    totalJobs > 0 ? (((stats?.failed_jobs ?? 0) / totalJobs) * 100).toFixed(2) : '0.00'

  const getServiceTypeName = (typeId: string) => {
    const st = serviceTypes.find((s) => s.id === typeId)
    return st?.display_name || typeId
  }

  const timeSince = (isoDate: string) => {
    const diff = Date.now() - new Date(isoDate).getTime()
    const mins = Math.floor(diff / 60000)
    if (mins < 1) return 'Just now'
    if (mins < 60) return `${mins}m ago`
    const hours = Math.floor(mins / 60)
    if (hours < 24) return `${hours}h ago`
    return `${Math.floor(hours / 24)}d ago`
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-foreground">System Health</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Real-time monitoring of worker nodes and services.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {activeInstances.length > 0 && (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-success/10 border border-success/20 rounded-full">
              <div className="w-2 h-2 rounded-full bg-success animate-pulse" />
              <span className="text-success text-xs font-medium">
                Systems Operational
              </span>
            </div>
          )}
          <ShadcnButton onClick={handleRefresh} disabled={refreshing} variant="secondary">
            <RefreshCw className={cn('h-4 w-4 mr-2', refreshing && 'animate-spin')} />
            Refresh
          </ShadcnButton>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <Card>
          <CardContent className="py-4 px-5">
            <div className="flex items-center justify-between mb-3">
              <div className="p-2 rounded-lg bg-primary/10">
                <Server className="h-5 w-5 text-primary" />
              </div>
            </div>
            <div className="text-xs text-muted-foreground uppercase tracking-wider">
              Active Workers
            </div>
            <div className="text-2xl font-bold text-foreground mt-1">
              {activeInstances.length}
            </div>
            <div className="text-xs text-muted-foreground mt-2">
              of {instances.length} total
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-4 px-5">
            <div className="flex items-center justify-between mb-3">
              <div className="p-2 rounded-lg bg-info/10">
                <Zap className="h-5 w-5 text-info" />
              </div>
            </div>
            <div className="text-xs text-muted-foreground uppercase tracking-wider">
              Avg Response
            </div>
            <div className="text-2xl font-bold text-foreground mt-1">
              {stats?.avg_processing_time_ms
                ? `${Math.round(stats.avg_processing_time_ms)}ms`
                : 'N/A'}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-4 px-5">
            <div className="flex items-center justify-between mb-3">
              <div className="p-2 rounded-lg bg-warning/10">
                <AlertOctagon className="h-5 w-5 text-warning" />
              </div>
            </div>
            <div className="text-xs text-muted-foreground uppercase tracking-wider">
              Pending Approvals
            </div>
            <div className="text-2xl font-bold text-foreground mt-1">
              {pendingServiceTypes.length}
            </div>
            {pendingServiceTypes.length > 0 && (
              <div className="text-xs text-warning mt-2">Action required</div>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-4 px-5">
            <div className="flex items-center justify-between mb-3">
              <div className="p-2 rounded-lg bg-destructive/10">
                <Activity className="h-5 w-5 text-destructive" />
              </div>
            </div>
            <div className="text-xs text-muted-foreground uppercase tracking-wider">
              Error Rate
            </div>
            <div className="text-2xl font-bold text-foreground mt-1">{errorRate}%</div>
            <div className="text-xs text-muted-foreground mt-2">
              {stats?.failed_jobs ?? 0} failed of {totalJobs} total
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Service Instances Table */}
      <Card className="mb-6">
        <CardContent className="pt-6">
          <h3 className="text-base font-semibold text-foreground mb-4">
            Service Instances
          </h3>
          {instances.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No service instances found.
            </div>
          ) : (
            <div className="rounded-md border border-border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Instance</TableHead>
                    <TableHead>Service Type</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Last Heartbeat</TableHead>
                    <TableHead>Current Job</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {instances.map((inst) => (
                    <TableRow key={inst.id}>
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <div className="p-2 rounded bg-muted text-muted-foreground">
                            <Server className="h-4 w-4" />
                          </div>
                          <div>
                            <div className="text-sm font-medium text-foreground">
                              {inst.id.length > 25
                                ? `${inst.id.slice(0, 25)}...`
                                : inst.id}
                            </div>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="text-sm">
                        {getServiceTypeName(inst.service_type_id)}
                      </TableCell>
                      <TableCell>
                        <span
                          className={cn(
                            'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium',
                            instanceStatusStyles[inst.status] ||
                              'bg-muted text-muted-foreground',
                          )}
                        >
                          <span
                            className={cn(
                              'w-1.5 h-1.5 rounded-full',
                              inst.status === 'ACTIVE'
                                ? 'bg-success'
                                : inst.status === 'PROCESSING'
                                  ? 'bg-processing'
                                  : inst.status === 'WAITING'
                                    ? 'bg-warning'
                                    : inst.status === 'DEAD'
                                      ? 'bg-destructive'
                                      : 'bg-muted-foreground',
                            )}
                          />
                          {inst.status}
                        </span>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {timeSince(inst.last_heartbeat_at)}
                      </TableCell>
                      <TableCell className="text-sm font-mono text-muted-foreground">
                        {inst.current_job_id
                          ? `${inst.current_job_id.slice(0, 8)}...`
                          : '-'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Pending Service Types */}
      {pendingServiceTypes.length > 0 && (
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold text-foreground">
                Pending Approvals
              </h3>
              <span className="bg-primary text-primary-foreground text-xs font-bold px-2 py-0.5 rounded-full">
                {pendingServiceTypes.length}
              </span>
            </div>
            <div className="space-y-3">
              {pendingServiceTypes.map((st) => (
                <div
                  key={st.id}
                  className="flex items-center justify-between p-4 rounded-lg border border-border bg-card"
                >
                  <div>
                    <div className="text-sm font-medium text-foreground">
                      {st.display_name || st.id}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {st.description || `Service type: ${st.id}`}
                    </div>
                    {st.dev_contact && (
                      <div className="text-xs text-muted-foreground mt-1">
                        Contact: {st.dev_contact}
                      </div>
                    )}
                  </div>
                  <span className="inline-flex items-center rounded-full bg-warning/20 text-warning px-2.5 py-0.5 text-xs font-medium">
                    PENDING
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
