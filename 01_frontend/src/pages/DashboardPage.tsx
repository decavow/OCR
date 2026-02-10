// Overview: recent batches, quick stats

import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Batch } from '../types'
import { getBatches } from '../api/batches'

export default function DashboardPage() {
  const [batches, setBatches] = useState<Batch[]>([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    const fetchBatches = async () => {
      try {
        const response = await getBatches(1, 5)
        setBatches(response.items)
      } catch {
        // Ignore error for dashboard
      } finally {
        setLoading(false)
      }
    }
    fetchBatches()
  }, [])

  const stats = {
    total: batches.length,
    processing: batches.filter((b) => b.status === 'PROCESSING').length,
    completed: batches.filter((b) => b.status === 'COMPLETED').length,
    failed: batches.filter((b) => b.status === 'FAILED').length,
  }

  return (
    <div className="dashboard-page">
      <div className="page-header">
        <h1>Dashboard</h1>
        <button className="primary" onClick={() => navigate('/upload')}>
          New Upload
        </button>
      </div>

      <div className="batch-info-grid">
        <div className="info-card">
          <div className="label">Total Batches</div>
          <div className="value">{stats.total}</div>
        </div>
        <div className="info-card">
          <div className="label">Processing</div>
          <div className="value">{stats.processing}</div>
        </div>
        <div className="info-card">
          <div className="label">Completed</div>
          <div className="value">{stats.completed}</div>
        </div>
        <div className="info-card">
          <div className="label">Failed</div>
          <div className="value">{stats.failed}</div>
        </div>
      </div>

      <h2>Recent Batches</h2>
      {loading ? (
        <div className="loading">Loading...</div>
      ) : batches.length === 0 ? (
        <div className="empty-state">
          <p>No batches yet. Upload some files to get started.</p>
        </div>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Request ID</th>
              <th>Status</th>
              <th>Files</th>
              <th>Created At</th>
            </tr>
          </thead>
          <tbody>
            {batches.map((batch) => (
              <tr key={batch.id} onClick={() => navigate(`/batches/${batch.id}`)}>
                <td>{batch.id.slice(0, 8)}...</td>
                <td>
                  <span className={`status-badge ${batch.status.toLowerCase()}`}>
                    {batch.status}
                  </span>
                </td>
                <td>
                  {batch.completed_files}/{batch.total_files}
                </td>
                <td>{new Date(batch.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
