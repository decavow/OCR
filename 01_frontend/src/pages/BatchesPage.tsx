import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Batch } from '../types'
import { getBatches, BatchFilters } from '../api/batches'
import { METHOD_OPTIONS } from '../config'
import { Button as ShadcnButton } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import ErrorMessage from '../components/common/ErrorMessage'
import BatchStatus from '../components/batch/BatchStatus'
import { SkeletonTable } from '../components/common/Skeleton'

const STATUS_OPTIONS = ['PROCESSING', 'COMPLETED', 'PARTIAL_SUCCESS', 'FAILED', 'CANCELLED']

export default function BatchesPage() {
  const [batches, setBatches] = useState<Batch[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filters, setFilters] = useState<BatchFilters>({})
  const navigate = useNavigate()
  const pageSize = 20

  const fetchBatches = useCallback(async () => {
    setLoading(true)
    try {
      const response = await getBatches(page, pageSize, filters)
      setBatches(response.items)
      setTotal(response.total)
    } catch {
      setError('Failed to load batches')
    } finally {
      setLoading(false)
    }
  }, [page, filters])

  useEffect(() => {
    fetchBatches()
  }, [fetchBatches])

  const handleFilterChange = (key: keyof BatchFilters, value: string) => {
    setPage(1)
    setFilters((prev) => ({
      ...prev,
      [key]: value || undefined,
    }))
  }

  const clearFilters = () => {
    setPage(1)
    setFilters({})
  }

  const hasFilters = Object.values(filters).some(Boolean)
  const totalPages = Math.ceil(total / pageSize)

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-foreground">Batches</h1>
        <ShadcnButton onClick={() => navigate('/upload')}>New Upload</ShadcnButton>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4 items-end">
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Status</label>
          <select
            className="h-9 rounded-md border border-input bg-background px-3 text-sm"
            value={filters.status || ''}
            onChange={(e) => handleFilterChange('status', e.target.value)}
          >
            <option value="">All</option>
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs text-muted-foreground mb-1">Method</label>
          <select
            className="h-9 rounded-md border border-input bg-background px-3 text-sm"
            value={filters.method || ''}
            onChange={(e) => handleFilterChange('method', e.target.value)}
          >
            <option value="">All</option>
            {METHOD_OPTIONS.map((m) => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs text-muted-foreground mb-1">From</label>
          <input
            type="date"
            className="h-9 rounded-md border border-input bg-background px-3 text-sm"
            value={filters.date_from || ''}
            onChange={(e) => handleFilterChange('date_from', e.target.value)}
          />
        </div>

        <div>
          <label className="block text-xs text-muted-foreground mb-1">To</label>
          <input
            type="date"
            className="h-9 rounded-md border border-input bg-background px-3 text-sm"
            value={filters.date_to || ''}
            onChange={(e) => handleFilterChange('date_to', e.target.value)}
          />
        </div>

        {hasFilters && (
          <ShadcnButton variant="ghost" size="sm" onClick={clearFilters}>
            Clear
          </ShadcnButton>
        )}
      </div>

      {loading ? (
        <SkeletonTable rows={5} cols={8} />
      ) : error ? (
        <ErrorMessage message={error} />
      ) : batches.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          {hasFilters ? 'No batches match the selected filters.' : 'No batches yet. Upload some files to get started.'}
        </div>
      ) : (
        <>
          <div className="rounded-md border border-border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Request ID</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Method</TableHead>
                  <TableHead>Files</TableHead>
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
                    <TableCell className="text-xs">{batch.method}</TableCell>
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

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-4">
              <span className="text-sm text-muted-foreground">
                Showing {(page - 1) * pageSize + 1}-{Math.min(page * pageSize, total)} of {total}
              </span>
              <div className="flex gap-2">
                <ShadcnButton
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                >
                  Previous
                </ShadcnButton>
                <ShadcnButton
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                </ShadcnButton>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
