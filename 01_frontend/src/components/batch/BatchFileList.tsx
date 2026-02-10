import { FileInfo, Job } from '../../types'

// Files within a batch (for batch detail view)
interface BatchFileListProps {
  files: FileInfo[]
  jobs: Job[]
  onFileSelect: (file: FileInfo) => void
}

export default function BatchFileList({ files, jobs, onFileSelect }: BatchFileListProps) {
  return (
    <div className="batch-file-list">
      {files.map((file) => {
        const job = jobs.find((j) => j.file_id === file.id)
        return (
          <div key={file.id} className="file-row" onClick={() => onFileSelect(file)}>
            <span className="file-name">{file.original_name}</span>
            <span className={`file-status ${job?.status.toLowerCase()}`}>
              {job?.status || 'PENDING'}
            </span>
          </div>
        )
      })}
    </div>
  )
}
