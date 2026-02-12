import { Batch } from '../../types'
import BatchStatus from './BatchStatus'
import { Card, CardContent } from '@/components/ui/card'

interface BatchCardProps {
  batch: Batch
  onClick?: () => void
}

export default function BatchCard({ batch, onClick }: BatchCardProps) {
  return (
    <Card
      className="cursor-pointer transition-colors hover:bg-accent/50"
      onClick={onClick}
    >
      <CardContent className="flex items-center justify-between py-4 px-5">
        <div className="flex items-center gap-4">
          <span className="text-sm font-mono text-foreground">{batch.id.slice(0, 8)}...</span>
          <span className="text-sm text-muted-foreground">
            {batch.completed_files}/{batch.total_files} files
          </span>
        </div>
        <div className="flex items-center gap-3">
          <BatchStatus status={batch.status} />
          <span className="text-xs text-muted-foreground">
            {new Date(batch.created_at).toLocaleDateString()}
          </span>
        </div>
      </CardContent>
    </Card>
  )
}
