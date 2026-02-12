import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { Batch } from '../types'
import { getBatches } from '../api/batches'
import { Button as ShadcnButton } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import Loading from '../components/common/Loading'
import BatchStatus from '../components/batch/BatchStatus'

export default function DashboardPage() {
  const [batches, setBatches] = useState<Batch[]>([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()
  const { user } = useAuth()

  // Redirect admin to admin dashboard
  useEffect(() => {
    if (user?.is_admin) {
      navigate('/admin/dashboard', { replace: true })
    }
  }, [user, navigate])

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
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-foreground">Dashboard</h1>
        <ShadcnButton onClick={() => navigate('/upload')}>New Upload</ShadcnButton>
      </div>

      <div className="grid grid-cols-4 gap-4 mb-8">
        {[
          { label: 'Total Batches', value: stats.total },
          { label: 'Processing', value: stats.processing },
          { label: 'Completed', value: stats.completed },
          { label: 'Failed', value: stats.failed },
        ].map((stat) => (
          <Card key={stat.label}>
            <CardContent className="py-4 px-5">
              <div className="text-sm text-muted-foreground">{stat.label}</div>
              <div className="text-2xl font-bold text-foreground mt-1">{stat.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <h2 className="text-lg font-semibold text-foreground mb-4">Recent Batches</h2>

      {loading ? (
        <Loading text="Loading..." />
      ) : batches.length === 0 ? (
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
                <TableHead>Files</TableHead>
                <TableHead>Created At</TableHead>
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
                  <TableCell>{batch.completed_files}/{batch.total_files}</TableCell>
                  <TableCell>{new Date(batch.created_at).toLocaleString()}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}
