import { Job } from '../../types'
import JobStatus from './JobStatus'

// Job row in batch detail (file name + status)
interface JobItemProps {
  job: Job
  fileName: string
  onClick?: () => void
}

export default function JobItem({ job, fileName, onClick }: JobItemProps) {
  return (
    <div className="job-item" onClick={onClick}>
      <span className="job-file-name">{fileName}</span>
      <JobStatus status={job.status} />
    </div>
  )
}
