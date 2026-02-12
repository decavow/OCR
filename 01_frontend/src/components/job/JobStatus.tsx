import { JobStatus as Status } from '../../types'
import { cn } from '@/lib/utils'

interface JobStatusProps {
  status: Status
}

const statusStyles: Record<string, string> = {
  submitted: 'bg-muted text-muted-foreground',
  validating: 'bg-primary/20 text-primary',
  queued: 'bg-muted text-muted-foreground',
  processing: 'bg-processing/20 text-processing',
  completed: 'bg-success/20 text-success',
  partial_success: 'bg-warning/20 text-warning',
  failed: 'bg-destructive/20 text-destructive',
  rejected: 'bg-destructive/20 text-destructive',
  cancelled: 'bg-muted text-muted-foreground',
  dead_letter: 'bg-destructive/20 text-destructive',
}

export default function JobStatus({ status }: JobStatusProps) {
  const key = status.toLowerCase()
  return (
    <span className={cn(
      'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium shrink-0',
      statusStyles[key] || 'bg-muted text-muted-foreground'
    )}>
      {status}
    </span>
  )
}
