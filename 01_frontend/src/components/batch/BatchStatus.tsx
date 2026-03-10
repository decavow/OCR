import { BatchStatus as Status } from '../../types'
import { cn } from '@/lib/utils'

interface BatchStatusProps {
  status: Status
}

const statusStyles: Record<string, string> = {
  processing: 'bg-processing/20 text-processing',
  completed: 'bg-success/20 text-success',
  partial_success: 'bg-warning/20 text-warning',
  failed: 'bg-destructive/20 text-destructive',
  cancelled: 'bg-muted text-muted-foreground',
  dead_letter: 'bg-destructive/30 text-destructive',
}

export default function BatchStatus({ status }: BatchStatusProps) {
  const key = status.toLowerCase()
  return (
    <span className={cn(
      'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
      statusStyles[key] || 'bg-muted text-muted-foreground'
    )}>
      {status}
    </span>
  )
}
