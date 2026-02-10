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

const STATUS_FILTERS = ['ALL', 'PENDING', 'APPROVED', 'DISABLED', 'REJECTED'] as const

function getStatusClass(status: string): string {
  switch (status) {
    case 'APPROVED': return 'status-badge completed'
    case 'PENDING': return 'status-badge pending'
    case 'DISABLED': return 'status-badge cancelled'
    case 'REJECTED': return 'status-badge failed'
    default: return 'status-badge'
  }
}

function getInstanceSummary(instanceCount: Record<string, number>): { text: string; cls: string } {
  const active = (instanceCount['ACTIVE'] || 0) + (instanceCount['PROCESSING'] || 0)
  const waiting = instanceCount['WAITING'] || 0
  const total = Object.values(instanceCount).reduce((a, b) => a + b, 0)

  if (active > 0) return { text: `${active} running`, cls: 'instance-running' }
  if (waiting > 0) return { text: `${waiting} waiting`, cls: 'instance-waiting' }
  if (total === 0) return { text: 'No instances', cls: 'instance-none' }
  return { text: `${total} stopped`, cls: 'instance-stopped' }
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
    <div className="admin-services-page">
      <div className="admin-page-header">
        <div>
          <h1>Service Management</h1>
          <p className="admin-page-subtitle">
            Manage OCR services, approve registrations, and control availability.
          </p>
        </div>
        {pendingCount > 0 && (
          <span className="pending-count-badge">{pendingCount} pending approval</span>
        )}
      </div>

      {error && <div className="error-message">{error}</div>}

      {/* Filter bar */}
      <div className="admin-filter-bar">
        {STATUS_FILTERS.map((s) => (
          <button
            key={s}
            className={`filter-btn ${filter === s ? 'active' : ''}`}
            onClick={() => setFilter(s)}
          >
            {s === 'ALL' ? 'All' : s.charAt(0) + s.slice(1).toLowerCase()}
          </button>
        ))}
        <button className="filter-btn refresh-btn" onClick={fetchServices} disabled={loading}>
          Refresh
        </button>
      </div>

      {/* Service table */}
      {loading ? (
        <div className="loading">Loading services...</div>
      ) : services.length === 0 ? (
        <div className="empty-state">No services found.</div>
      ) : (
        <div className="admin-table-wrapper">
          <table className="data-table admin-table">
            <thead>
              <tr>
                <th>Service</th>
                <th>Methods / Tiers</th>
                <th>Instances</th>
                <th>Status</th>
                <th>Approved By</th>
                <th className="actions-col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {services.map((svc) => {
                const inst = getInstanceSummary(svc.instance_count)
                const isLoading = actionLoading === svc.id
                return (
                  <tr key={svc.id} className={svc.status === 'PENDING' ? 'pending-row' : ''}>
                    <td>
                      <div className="svc-name">{svc.display_name}</div>
                      <code className="svc-id">{svc.id}</code>
                    </td>
                    <td>
                      <div className="svc-tags">
                        {svc.allowed_methods.map((m) => (
                          <span key={m} className="svc-tag method-tag">{m}</span>
                        ))}
                        {svc.allowed_tiers.map((t) => (
                          <span key={t} className="svc-tag tier-tag">tier {t}</span>
                        ))}
                      </div>
                    </td>
                    <td>
                      <span className={`instance-badge ${inst.cls}`}>{inst.text}</span>
                    </td>
                    <td>
                      <span className={getStatusClass(svc.status)}>{svc.status}</span>
                    </td>
                    <td className="approved-by-cell">
                      {svc.approved_by || '-'}
                    </td>
                    <td className="actions-col">
                      <div className="action-buttons">
                        {svc.status === 'PENDING' && (
                          <>
                            <button
                              className="action-btn approve-btn"
                              onClick={() => handleApprove(svc.id)}
                              disabled={isLoading}
                            >
                              Approve
                            </button>
                            <button
                              className="action-btn reject-btn"
                              onClick={() => setRejectModal({ id: svc.id, name: svc.display_name })}
                              disabled={isLoading}
                            >
                              Reject
                            </button>
                          </>
                        )}
                        {svc.status === 'APPROVED' && (
                          <button
                            className="action-btn disable-btn"
                            onClick={() => handleDisable(svc.id)}
                            disabled={isLoading}
                          >
                            Disable
                          </button>
                        )}
                        {svc.status === 'DISABLED' && (
                          <button
                            className="action-btn enable-btn"
                            onClick={() => handleEnable(svc.id)}
                            disabled={isLoading}
                          >
                            Enable
                          </button>
                        )}
                        {(svc.status === 'REJECTED' || svc.status === 'DISABLED') && (
                          <button
                            className="action-btn delete-btn"
                            onClick={() => handleDelete(svc.id, svc.display_name)}
                            disabled={isLoading}
                          >
                            Delete
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Reject Modal */}
      {rejectModal && (
        <div className="modal-overlay" onClick={() => setRejectModal(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h3>Reject "{rejectModal.name}"</h3>
            <p className="modal-hint">This is a terminal action. The service must be deleted and re-registered to try again.</p>
            <div className="form-group">
              <label htmlFor="reject-reason">Reason</label>
              <textarea
                id="reject-reason"
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="Provide a reason for rejection..."
                rows={3}
              />
            </div>
            <div className="modal-actions">
              <button className="action-btn" onClick={() => setRejectModal(null)}>Cancel</button>
              <button
                className="action-btn reject-btn"
                onClick={handleReject}
                disabled={!rejectReason.trim() || actionLoading === rejectModal.id}
              >
                Reject Service
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
