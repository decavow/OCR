import { Batch } from '../../types'
import BatchStatus from './BatchStatus'

// Batch summary: file count, status, date
interface BatchCardProps {
  batch: Batch
  onClick?: () => void
}

export default function BatchCard({ batch, onClick }: BatchCardProps) {
  return (
    <div className="batch-card" onClick={onClick}>
      <div className="batch-info">
        <span className="batch-id">{batch.id.slice(0, 8)}...</span>
        <span className="batch-files">
          {batch.completed_files}/{batch.total_files} files
        </span>
      </div>
      <div className="batch-meta">
        <BatchStatus status={batch.status} />
        <span className="batch-date">
          {new Date(batch.created_at).toLocaleDateString()}
        </span>
      </div>
    </div>
  )
}
