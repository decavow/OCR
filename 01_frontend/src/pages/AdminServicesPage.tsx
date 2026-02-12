import { useState, useEffect, useCallback } from 'react'
import {
  getServiceTypes,
  approveServiceType,
  rejectServiceType,
  disableServiceType,
  enableServiceType,
  deleteServiceType,
  ServiceType,
} from '../api/admin'
import { Button as ShadcnButton } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'
import { RefreshCw } from 'lucide-react'
import Loading from '../components/common/Loading'

const STATUS_FILTERS = ['ALL', 'PENDING', 'APPROVED', 'DISABLED', 'REJECTED'] as const

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

  if (active > 0) return { text: `${active} running`, cls: 'text-success' }
  if (waiting > 0) return { text: `${waiting} waiting`, cls: 'text-warning' }
  if (total === 0) return { text: 'No instances', cls: 'text-muted-foreground' }
  return { text: `${total} stopped`, cls: 'text-destructive' }
}

export default function AdminServicesPage() {
  const [services, setServices] = useState<ServiceType[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<string>('ALL')
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [rejectModal, setRejectModal] = useState<{ id: string; name: string } | null>(null)
  const [rejectReason, setRejectReason] = useState('')

  const fetchServices = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const status = filter === 'ALL' ? undefined : filter
      const res = await getServiceTypes(status)
      setServices(res.items)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load services')
    } finally {
      setLoading(false)
    }
  }, [filter])

  useEffect(() => { fetchServices() }, [fetchServices])

  const handleAction = async (action: () => Promise<unknown>) => {
    try {
      await action()
      await fetchServices()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Action failed')
    } finally {
      setActionLoading(null)
    }
  }

  const handleApprove = (id: string) => {
    setActionLoading(id)
    handleAction(() => approveServiceType(id))
  }

  const handleReject = () => {
    if (!rejectModal || !rejectReason.trim()) return
    setActionLoading(rejectModal.id)
    handleAction(() => rejectServiceType(rejectModal.id, rejectReason))
      .then(() => { setRejectModal(null); setRejectReason('') })
  }

  const handleDisable = (id: string) => {
    setActionLoading(id)
    handleAction(() => disableServiceType(id))
  }

  const handleEnable = (id: string) => {
    setActionLoading(id)
    handleAction(() => enableServiceType(id))
  }

  const handleDelete = (id: string, name: string) => {
    if (!window.confirm(`Delete service "${name}"? This cannot be undone.`)) return
    setActionLoading(id)
    handleAction(() => deleteServiceType(id))
  }

  const pendingCount = services.filter((s) => s.status === 'PENDING').length

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Service Management</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Manage OCR services, approve registrations, and control availability.
          </p>
        </div>
        {pendingCount > 0 && (
          <span className="inline-flex items-center rounded-full bg-warning/20 text-warning px-3 py-1 text-sm font-medium">
            {pendingCount} pending approval
          </span>
        )}
      </div>

      {error && (
        <div className="text-sm text-destructive bg-destructive/10 border border-destructive/30 rounded-md p-3 mb-4">
          {error}
        </div>
      )}

      {/* Filter bar */}
      <div className="flex items-center gap-2 mb-4">
        {STATUS_FILTERS.map((s) => (
          <ShadcnButton
            key={s}
            variant={filter === s ? 'default' : 'secondary'}
            size="sm"
            onClick={() => setFilter(s)}
          >
            {s === 'ALL' ? 'All' : s.charAt(0) + s.slice(1).toLowerCase()}
          </ShadcnButton>
        ))}
        <ShadcnButton variant="ghost" size="sm" onClick={fetchServices} disabled={loading}>
          <RefreshCw className={cn('h-4 w-4', loading && 'animate-spin')} />
        </ShadcnButton>
      </div>

      {/* Service table */}
      {loading ? (
        <Loading text="Loading services..." />
      ) : services.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">No services found.</div>
      ) : (
        <div className="rounded-md border border-border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Service</TableHead>
                <TableHead>Methods / Tiers</TableHead>
                <TableHead>Instances</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Approved By</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {services.map((svc) => {
                const inst = getInstanceSummary(svc.instance_count)
                const isLoading = actionLoading === svc.id
                return (
                  <TableRow key={svc.id} className={svc.status === 'PENDING' ? 'bg-warning/5' : ''}>
                    <TableCell>
                      <div className="text-sm font-medium text-foreground">{svc.display_name}</div>
                      <code className="text-xs text-muted-foreground">{svc.id}</code>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {svc.allowed_methods.map((m) => (
                          <span key={m} className="inline-flex items-center rounded bg-primary/20 text-primary px-1.5 py-0.5 text-xs">
                            {m}
                          </span>
                        ))}
                        {svc.allowed_tiers.map((t) => (
                          <span key={t} className="inline-flex items-center rounded bg-muted text-muted-foreground px-1.5 py-0.5 text-xs">
                            tier {t}
                          </span>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className={cn('text-sm font-medium', inst.cls)}>{inst.text}</span>
                    </TableCell>
                    <TableCell>
                      <span className={cn(
                        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
                        statusStyles[svc.status] || 'bg-muted text-muted-foreground'
                      )}>
                        {svc.status}
                      </span>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {svc.approved_by || '-'}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        {svc.status === 'PENDING' && (
                          <>
                            <ShadcnButton size="sm" onClick={() => handleApprove(svc.id)} disabled={isLoading}>
                              Approve
                            </ShadcnButton>
                            <ShadcnButton
                              variant="destructive"
                              size="sm"
                              onClick={() => setRejectModal({ id: svc.id, name: svc.display_name })}
                              disabled={isLoading}
                            >
                              Reject
                            </ShadcnButton>
                          </>
                        )}
                        {svc.status === 'APPROVED' && (
                          <ShadcnButton variant="secondary" size="sm" onClick={() => handleDisable(svc.id)} disabled={isLoading}>
                            Disable
                          </ShadcnButton>
                        )}
                        {svc.status === 'DISABLED' && (
                          <ShadcnButton variant="secondary" size="sm" onClick={() => handleEnable(svc.id)} disabled={isLoading}>
                            Enable
                          </ShadcnButton>
                        )}
                        {(svc.status === 'REJECTED' || svc.status === 'DISABLED') && (
                          <ShadcnButton variant="destructive" size="sm" onClick={() => handleDelete(svc.id, svc.display_name)} disabled={isLoading}>
                            Delete
                          </ShadcnButton>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Reject Modal */}
      <Dialog open={!!rejectModal} onOpenChange={(open) => !open && setRejectModal(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reject "{rejectModal?.name}"</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            This is a terminal action. The service must be deleted and re-registered to try again.
          </p>
          <div className="space-y-2 mt-4">
            <Label htmlFor="reject-reason">Reason</Label>
            <textarea
              id="reject-reason"
              className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Provide a reason for rejection..."
            />
          </div>
          <div className="flex justify-end gap-2 mt-4">
            <ShadcnButton variant="secondary" onClick={() => setRejectModal(null)}>Cancel</ShadcnButton>
            <ShadcnButton
              variant="destructive"
              onClick={handleReject}
              disabled={!rejectReason.trim() || actionLoading === rejectModal?.id}
            >
              Reject Service
            </ShadcnButton>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
