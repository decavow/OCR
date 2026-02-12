import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Users,
  FileText,
  CheckCircle,
  AlertTriangle,
  Clock,
  TrendingUp,
  RefreshCw,
} from 'lucide-react'
import {
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
  Cell,
} from 'recharts'
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
import BatchStatus from '../components/batch/BatchStatus'
import {
  getAdminStats,
  getAdminRecentRequests,
  getAdminJobVolume,
  getServiceTypes,
  AdminStats,
  AdminRequestItem,
  JobVolumePoint,
  ServiceType,
} from '../api/admin'

const statusStyles: Record<string, string> = {
  APPROVED: 'bg-success/20 text-success',
  PENDING: 'bg-warning/20 text-warning',
  DISABLED: 'bg-muted text-muted-foreground',
  REJECTED: 'bg-destructive/20 text-destructive',
}

function getInstanceSummary(instanceCount: Record<string, number>): { text: string; cls: string } {
  const active = (instanceCount['ACTIVE'] || 0) + (instanceCount['PROCESSING'] || 0)
  const waiting = instanceCount['WAITING'] || 0
  const total = Object.values(instanceCount).reduce((a, b) => a + b, 0)

  if (active > 0) return { text: `${active} active`, cls: 'text-success' }
  if (waiting > 0) return { text: `${waiting} waiting`, cls: 'text-warning' }
  if (total === 0) return { text: 'No instances', cls: 'text-muted-foreground' }
  return { text: `${total} stopped`, cls: 'text-destructive' }
}

export default function AdminDashboardPage() {
  const navigate = useNavigate()
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [requests, setRequests] = useState<AdminRequestItem[]>([])
  const [volume, setVolume] = useState<JobVolumePoint[]>([])
  const [services, setServices] = useState<ServiceType[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const fetchData = useCallback(async () => {
    try {
      const [statsRes, reqRes, volRes, svcRes] = await Promise.all([
        getAdminStats(),
        getAdminRecentRequests(1, 10),
        getAdminJobVolume(24),
        getServiceTypes(),
      ])
      setStats(statsRes)
      setRequests(reqRes.items)
      setVolume(volRes.data)
      setServices(svcRes.items)
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

  if (loading) return <Loading text="Loading dashboard..." />

  const kpis = [
    {
      label: 'Total Users',
      value: stats?.total_users ?? 0,
      icon: Users,
      iconClass: 'text-primary',
      bgClass: 'bg-primary/10',
    },
    {
      label: 'Total Requests',
      value: stats?.total_requests ?? 0,
      icon: FileText,
      iconClass: 'text-info',
      bgClass: 'bg-info/10',
    },
    {
      label: 'Completed Jobs',
      value: stats?.completed_jobs ?? 0,
      icon: CheckCircle,
      iconClass: 'text-success',
      bgClass: 'bg-success/10',
    },
    {
      label: 'Failed Jobs',
      value: stats?.failed_jobs ?? 0,
      icon: AlertTriangle,
      iconClass: 'text-destructive',
      bgClass: 'bg-destructive/10',
    },
  ]

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Dashboard Overview</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Real-time monitoring of OCR processing health.
          </p>
        </div>
        <ShadcnButton onClick={handleRefresh} disabled={refreshing} variant="secondary">
          <RefreshCw className={cn('h-4 w-4 mr-2', refreshing && 'animate-spin')} />
          Refresh
        </ShadcnButton>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {kpis.map((kpi) => (
          <Card key={kpi.label}>
            <CardContent className="py-4 px-5">
              <div className="flex items-center justify-between mb-3">
                <div className={cn('p-2 rounded-lg', kpi.bgClass)}>
                  <kpi.icon className={cn('h-5 w-5', kpi.iconClass)} />
                </div>
                {kpi.label === 'Completed Jobs' && stats && stats.total_jobs > 0 && (
                  <span className="text-xs font-medium text-success bg-success/10 px-2 py-0.5 rounded-full">
                    {stats.success_rate}%
                  </span>
                )}
              </div>
              <div className="text-sm text-muted-foreground">{kpi.label}</div>
              <div className="text-2xl font-bold text-foreground mt-1">
                {kpi.value.toLocaleString()}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Extra stats row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <Card>
          <CardContent className="py-4 px-5 flex items-center gap-3">
            <div className="p-2 rounded-lg bg-primary/10">
              <Clock className="h-5 w-5 text-primary" />
            </div>
            <div>
              <div className="text-sm text-muted-foreground">Avg Processing Time</div>
              <div className="text-xl font-bold text-foreground">
                {stats?.avg_processing_time_ms
                  ? `${Math.round(stats.avg_processing_time_ms)}ms`
                  : 'N/A'}
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-4 px-5 flex items-center gap-3">
            <div className="p-2 rounded-lg bg-processing/10">
              <TrendingUp className="h-5 w-5 text-processing" />
            </div>
            <div>
              <div className="text-sm text-muted-foreground">Processing Now</div>
              <div className="text-xl font-bold text-foreground">
                {stats?.processing_jobs ?? 0}
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-4 px-5 flex items-center gap-3">
            <div className="p-2 rounded-lg bg-success/10">
              <CheckCircle className="h-5 w-5 text-success" />
            </div>
            <div>
              <div className="text-sm text-muted-foreground">Success Rate</div>
              <div className="text-xl font-bold text-foreground">
                {stats?.success_rate ?? 0}%
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Chart */}
      {volume.length > 0 && (
        <Card className="mb-6">
          <CardContent className="pt-6">
            <div className="flex justify-between items-center mb-4">
              <div>
                <h3 className="text-base font-semibold text-foreground">
                  Job Volume vs. Processing Time
                </h3>
                <p className="text-sm text-muted-foreground">Last 24 hours</p>
              </div>
              <div className="flex gap-4">
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full bg-primary" />
                  <span className="text-xs text-muted-foreground">Volume</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full bg-success" />
                  <span className="text-xs text-muted-foreground">Latency</span>
                </div>
              </div>
            </div>
            <div className="h-[280px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={volume}>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'hsl(var(--card))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px',
                      color: 'hsl(var(--foreground))',
                    }}
                  />
                  <XAxis
                    dataKey="hour"
                    stroke="hsl(var(--muted-foreground))"
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    yAxisId="left"
                    stroke="hsl(var(--muted-foreground))"
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    stroke="hsl(var(--muted-foreground))"
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                    unit="ms"
                  />
                  <Bar
                    yAxisId="left"
                    dataKey="volume"
                    barSize={20}
                    fill="hsl(var(--primary))"
                    radius={[4, 4, 0, 0]}
                  >
                    {volume.map((_, index) => (
                      <Cell key={`cell-${index}`} fillOpacity={0.6} />
                    ))}
                  </Bar>
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="avg_latency_ms"
                    stroke="hsl(var(--success))"
                    strokeWidth={2}
                    dot={false}
                    name="Latency (ms)"
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Services Health */}
      {services.length > 0 && (
        <Card className="mb-6">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold text-foreground">
                Services Health
              </h3>
              <ShadcnButton
                variant="ghost"
                size="sm"
                onClick={() => navigate('/admin/services')}
              >
                Manage
              </ShadcnButton>
            </div>
            <div className="rounded-md border border-border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Service</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Instances</TableHead>
                    <TableHead>Methods</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {services.map((svc) => {
                    const inst = getInstanceSummary(svc.instance_count)
                    return (
                      <TableRow key={svc.id}>
                        <TableCell>
                          <div className="text-sm font-medium text-foreground">
                            {svc.display_name || svc.id}
                          </div>
                          <code className="text-xs text-muted-foreground">{svc.id}</code>
                        </TableCell>
                        <TableCell>
                          <span
                            className={cn(
                              'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
                              statusStyles[svc.status] ||
                                'bg-muted text-muted-foreground',
                            )}
                          >
                            {svc.status}
                          </span>
                        </TableCell>
                        <TableCell>
                          <span className={cn('text-sm font-medium', inst.cls)}>
                            {inst.text}
                          </span>
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-wrap gap-1">
                            {svc.allowed_methods.map((m) => (
                              <span
                                key={m}
                                className="inline-flex items-center rounded bg-primary/20 text-primary px-1.5 py-0.5 text-xs"
                              >
                                {m}
                              </span>
                            ))}
                          </div>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Recent Requests */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-base font-semibold text-foreground">
              Recent Requests (All Users)
            </h3>
          </div>
          {requests.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No requests yet.
            </div>
          ) : (
            <div className="rounded-md border border-border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Request ID</TableHead>
                    <TableHead>User</TableHead>
                    <TableHead>Method</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Files</TableHead>
                    <TableHead>Created At</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {requests.map((r) => (
                    <TableRow key={r.id}>
                      <TableCell className="font-mono text-sm">
                        {r.id.slice(0, 8)}...
                      </TableCell>
                      <TableCell className="text-sm">{r.user_email}</TableCell>
                      <TableCell>
                        <span className="inline-flex items-center rounded bg-primary/20 text-primary px-1.5 py-0.5 text-xs">
                          {r.method}
                        </span>
                      </TableCell>
                      <TableCell>
                        <BatchStatus status={r.status as any} />
                      </TableCell>
                      <TableCell className="text-sm">
                        {r.completed_files}/{r.total_files}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {new Date(r.created_at).toLocaleString()}
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
