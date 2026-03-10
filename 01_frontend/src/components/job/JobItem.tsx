import { Job } from '../../types'
import JobStatus from './JobStatus'

interface JobItemProps {
  job: Job
  fileName: string
  onClick?: () => void
}

export default function JobItem({ job, fileName, onClick }: JobItemProps) {
  return (
    <div
      className="flex items-center justify-between py-2 px-3 rounded-md cursor-pointer hover:bg-muted transition-colors"
      onClick={onClick}
    >
      <span className="text-sm text-foreground truncate">{fileName}</span>
      <div className="flex items-center gap-2 shrink-0">
        {job.retry_count > 0 && (
          <span className="text-xs text-warning">
            Retry {job.retry_count}/{job.max_retries}
          </span>
        )}
        <JobStatus status={job.status} />
      </div>
    </div>
  )
}
