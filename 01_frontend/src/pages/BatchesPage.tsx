import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Batch } from '../types'
import { getBatches } from '../api/batches'
import { Button as ShadcnButton } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import Loading from '../components/common/Loading'
import ErrorMessage from '../components/common/ErrorMessage'
import BatchStatus from '../components/batch/BatchStatus'

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

  if (loading) return <Loading text="Loading..." />
  if (error) return <ErrorMessage message={error} />

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-foreground">Batches</h1>
        <ShadcnButton onClick={() => navigate('/upload')}>New Upload</ShadcnButton>
      </div>

      {batches.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          No batches yet. Upload some files to get started.
        </div>
      ) : (
        <div className="rounded-md border border-border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Request ID</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Total Files</TableHead>
                <TableHead>Completed</TableHead>
                <TableHead>Failed</TableHead>
                <TableHead>Created At</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {batches.map((batch) => (
                <TableRow
                  key={batch.id}
                  className="cursor-pointer"
                  onClick={() => navigate(`/batches/${batch.id}`)}
                >
                  <TableCell className="font-mono">{batch.id.slice(0, 8)}...</TableCell>
                  <TableCell>
                    <BatchStatus status={batch.status} />
                  </TableCell>
                  <TableCell>{batch.total_files}</TableCell>
                  <TableCell>{batch.completed_files}</TableCell>
                  <TableCell>{batch.failed_files}</TableCell>
                  <TableCell>{new Date(batch.created_at).toLocaleString()}</TableCell>
                  <TableCell>
                    <ShadcnButton
                      variant="ghost"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation()
                        navigate(`/batches/${batch.id}`)
                      }}
                    >
                      View
                    </ShadcnButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}
