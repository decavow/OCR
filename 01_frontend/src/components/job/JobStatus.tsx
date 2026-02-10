import { JobStatus as Status } from '../../types'

// All states: SUBMITTED, VALIDATING, QUEUED, PROCESSING, COMPLETED,
// PARTIAL_SUCCESS, FAILED, REJECTED, CANCELLED, DEAD_LETTER

interface JobStatusProps {
  status: Status
}

export default function JobStatus({ status }: JobStatusProps) {
  // TODO: Render status badge with appropriate color
  return <span className={`job-status ${status.toLowerCase()}`}>{status}</span>
}
