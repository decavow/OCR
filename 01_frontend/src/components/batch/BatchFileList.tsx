import { FileInfo, Job } from '../../types'
import { cn } from '@/lib/utils'

interface BatchFileListProps {
  files: FileInfo[]
  jobs: Job[]
  onFileSelect: (file: FileInfo) => void
}

const statusStyles: Record<string, string> = {
  completed: 'text-success',
  processing: 'text-processing',
  failed: 'text-destructive',
  submitted: 'text-muted-foreground',
}

export default function BatchFileList({ files, jobs, onFileSelect }: BatchFileListProps) {
  return (
    <div className="flex flex-col gap-1">
      {files.map((file) => {
        const job = jobs.find((j) => j.file_id === file.id)
        const status = job?.status || 'PENDING'
        return (
          <div
            key={file.id}
            className="flex items-center justify-between py-2 px-3 rounded-md cursor-pointer hover:bg-muted transition-colors"
            onClick={() => onFileSelect(file)}
          >
            <span className="text-sm text-foreground truncate">{file.original_name}</span>
            <span className={cn(
              'text-xs font-medium',
              statusStyles[status.toLowerCase()] || 'text-muted-foreground'
            )}>
              {status}
            </span>
          </div>
        )
      })}
    </div>
  )
}
