import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import BatchStatus from '../components/batch/BatchStatus'
import JobStatus from '../components/job/JobStatus'
import { Job } from '../types'
import { getBatch, cancelBatch, BatchDetail } from '../api/batches'
import { POLLING_INTERVAL } from '../config'
import { Card, CardContent } from '@/components/ui/card'
import { Button as ShadcnButton } from '@/components/ui/button'
import Loading from '../components/common/Loading'
import ErrorMessage from '../components/common/ErrorMessage'

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

  if (loading) return <Loading text="Loading..." />
  if (error) return <ErrorMessage message={error} />
  if (!batch) return <ErrorMessage message="Batch not found" />

  return (
    <div>
      <div className="flex items-center gap-4 mb-6">
        <h1 className="text-2xl font-bold text-foreground">Batch Details</h1>
        <BatchStatus status={batch.status} />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {[
          { label: 'ID', value: `${batch.id.slice(0, 8)}...` },
          { label: 'Files', value: `${batch.completed_files}/${batch.total_files} completed` },
          { label: 'Format', value: batch.output_format.toUpperCase() },
          { label: 'Created', value: new Date(batch.created_at).toLocaleString() },
        ].map((item) => (
          <Card key={item.label}>
            <CardContent className="py-3 px-4">
              <div className="text-xs text-muted-foreground">{item.label}</div>
              <div className="text-sm font-medium text-foreground mt-1">{item.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="mb-6">
        <h2 className="text-lg font-semibold text-foreground mb-3">Jobs</h2>
        <div className="flex flex-col gap-1 rounded-md border border-border overflow-hidden">
          {batch.jobs.map((job) => (
            <div
              key={job.id}
              className="flex items-center justify-between py-3 px-4 hover:bg-muted transition-colors"
              onClick={() => handleJobSelect(job)}
              style={{ cursor: job.status === 'COMPLETED' ? 'pointer' : 'default' }}
            >
              <span className="text-sm font-mono text-foreground">
                File {job.file_id.slice(0, 8)}...
              </span>
              <div className="flex items-center gap-3">
                <JobStatus status={job.status} />
                {job.processing_time_ms && (
                  <span className="text-xs text-muted-foreground">{job.processing_time_ms}ms</span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {batch.status === 'PROCESSING' && (
        <ShadcnButton variant="destructive" onClick={handleCancel}>
          Cancel Batch
        </ShadcnButton>
      )}
    </div>
  )
}
