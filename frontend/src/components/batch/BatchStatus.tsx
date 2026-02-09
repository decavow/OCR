import { BatchStatus as Status } from '../../types'

// Status badge (Processing, Completed, Partial Success, Failed, Cancelled)
interface BatchStatusProps {
  status: Status
}

export default function BatchStatus({ status }: BatchStatusProps) {
  // TODO: Render status badge with appropriate color
  return <span className={`batch-status ${status.toLowerCase()}`}>{status}</span>
}
