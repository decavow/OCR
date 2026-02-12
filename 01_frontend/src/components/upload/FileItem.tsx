import { UploadFile } from '../../types'
import { cn } from '@/lib/utils'
import { X } from 'lucide-react'
import { Button as ShadcnButton } from '@/components/ui/button'

interface FileItemProps {
  file: UploadFile
  onRemove: () => void
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const statusStyles = {
  pending: 'bg-muted/50 text-muted-foreground',
  uploading: 'bg-primary/20 text-primary',
  completed: 'bg-success/20 text-success',
  error: 'bg-destructive/20 text-destructive',
}

const statusLabels = {
  pending: 'Pending',
  uploading: 'Uploading...',
  completed: 'Uploaded',
  error: 'Error',
}

export default function FileItem({ file, onRemove }: FileItemProps) {
  return (
    <div className="flex items-center justify-between py-2 px-3 rounded-md bg-card border border-border">
      <div className="flex items-center gap-3 min-w-0 flex-1">
        <span className="text-sm font-medium text-foreground truncate">{file.file.name}</span>
        <span className="text-xs text-muted-foreground shrink-0">{formatFileSize(file.file.size)}</span>
        <span className="text-xs text-muted-foreground shrink-0">{file.file.type || 'Unknown'}</span>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        <span
          className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium', statusStyles[file.status])}
          title={file.status === 'error' ? file.error : undefined}
        >
          {statusLabels[file.status]}
        </span>

        {file.status === 'pending' && (
          <ShadcnButton variant="ghost" size="icon" className="h-6 w-6" onClick={onRemove} title="Remove file">
            <X className="h-3 w-3" />
          </ShadcnButton>
        )}
      </div>
    </div>
  )
}
