// Single batch: file list + statuses

import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import BatchStatus from '../components/batch/BatchStatus'
import { Job } from '../types'
import { getBatch, cancelBatch, BatchDetail } from '../api/batches'
import { POLLING_INTERVAL } from '../config'

export default function BatchDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [batch, setBatch] = useState<BatchDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchBatch = useCallback(async () => {
    if (!id) return
    try {
      const data = await getBatch(id)
      setBatch(data)
    } catch {
      setError('Failed to load batch')
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    fetchBatch()

    // Poll for updates if batch is still processing
    const interval = setInterval(() => {
      if (batch && !['COMPLETED', 'FAILED', 'CANCELLED'].includes(batch.status)) {
        fetchBatch()
      }
    }, POLLING_INTERVAL)

    return () => clearInterval(interval)
  }, [fetchBatch, batch?.status])

  const handleJobSelect = (job: Job) => {
    if (job.status === 'COMPLETED') {
      navigate(`/batches/${id}/files/${job.file_id}`)
    }
  }

  const handleCancel = async () => {
    if (!id) return
    try {
      await cancelBatch(id)
      fetchBatch()
    } catch {
      setError('Failed to cancel batch')
    }
  }

  if (loading) return <div className="loading">Loading...</div>
  if (error) return <div className="error-message">{error}</div>
  if (!batch) return <div className="error-message">Batch not found</div>

  return (
    <div className="batch-detail-page">
      <div className="page-header">
        <h1>Batch Details</h1>
        <BatchStatus status={batch.status} />
      </div>

      <div className="batch-info">
        <div className="info-item">
          <span className="label">ID:</span>
          <span className="value">{batch.id.slice(0, 8)}...</span>
        </div>
        <div className="info-item">
          <span className="label">Files:</span>
          <span className="value">
            {batch.completed_files}/{batch.total_files} completed
          </span>
        </div>
        <div className="info-item">
          <span className="label">Format:</span>
          <span className="value">{batch.output_format.toUpperCase()}</span>
        </div>
        <div className="info-item">
          <span className="label">Created:</span>
          <span className="value">
            {new Date(batch.created_at).toLocaleString()}
          </span>
        </div>
      </div>

      <div className="jobs-section">
        <h2>Jobs</h2>
        <div className="jobs-list">
          {batch.jobs.map((job) => (
            <div
              key={job.id}
              className={`job-item status-${job.status.toLowerCase()}`}
              onClick={() => handleJobSelect(job)}
              style={{ cursor: job.status === 'COMPLETED' ? 'pointer' : 'default' }}
            >
              <span className="job-file">File {job.file_id.slice(0, 8)}...</span>
              <span className={`job-status ${job.status.toLowerCase()}`}>
                {job.status}
              </span>
              {job.processing_time_ms && (
                <span className="job-time">{job.processing_time_ms}ms</span>
              )}
            </div>
          ))}
        </div>
      </div>

      {batch.status === 'PROCESSING' && (
        <div className="batch-actions">
          <button className="danger" onClick={handleCancel}>
            Cancel Batch
          </button>
        </div>
      )}
    </div>
  )
}
