// All batches list (nav: "Batches")

import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Batch } from '../types'
import { getBatches } from '../api/batches'

export default function BatchesPage() {
  const [batches, setBatches] = useState<Batch[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    const fetchBatches = async () => {
      try {
        const response = await getBatches()
        setBatches(response.items)
      } catch {
        setError('Failed to load batches')
      } finally {
        setLoading(false)
      }
    }
    fetchBatches()
  }, [])

  const handleRowClick = (batch: Batch) => {
    navigate(`/batches/${batch.id}`)
  }

  if (loading) return <div className="loading">Loading...</div>
  if (error) return <div className="error-message">{error}</div>

  return (
    <div className="batches-page">
      <div className="page-header">
        <h1>Batches</h1>
        <button className="primary" onClick={() => navigate('/upload')}>
          New Upload
        </button>
      </div>

      {batches.length === 0 ? (
        <div className="empty-state">
          <p>No batches yet. Upload some files to get started.</p>
        </div>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Request ID</th>
              <th>Status</th>
              <th>Total Files</th>
              <th>Completed</th>
              <th>Failed</th>
              <th>Created At</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {batches.map((batch) => (
              <tr key={batch.id} onClick={() => handleRowClick(batch)}>
                <td>{batch.id.slice(0, 8)}...</td>
                <td>
                  <span className={`status-badge ${batch.status.toLowerCase()}`}>
                    {batch.status}
                  </span>
                </td>
                <td>{batch.total_files}</td>
                <td>{batch.completed_files}</td>
                <td>{batch.failed_files}</td>
                <td>{new Date(batch.created_at).toLocaleString()}</td>
                <td>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      navigate(`/batches/${batch.id}`)
                    }}
                  >
                    View
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
