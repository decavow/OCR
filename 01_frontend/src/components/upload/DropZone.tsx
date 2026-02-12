import { useRef, useState, DragEvent, ChangeEvent } from 'react'
import { ALLOWED_FILE_TYPES } from '../../config'
import { cn } from '@/lib/utils'
import { Upload } from 'lucide-react'

interface DropZoneProps {
  onFilesSelected: (files: File[]) => void
  disabled?: boolean
}

export default function DropZone({ onFilesSelected, disabled }: DropZoneProps) {
  const [isDragOver, setIsDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleDragOver = (e: DragEvent) => {
    e.preventDefault()
    if (!disabled) setIsDragOver(true)
  }

  const handleDragLeave = (e: DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
  }

  const handleDrop = (e: DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
    if (disabled) return

    const droppedFiles = Array.from(e.dataTransfer.files)
    const validFiles = droppedFiles.filter((file) =>
      ALLOWED_FILE_TYPES.includes(file.type)
    )
    if (validFiles.length > 0) onFilesSelected(validFiles)
  }

  const handleClick = () => {
    if (!disabled) inputRef.current?.click()
  }

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      onFilesSelected(Array.from(e.target.files))
      e.target.value = ''
    }
  }

  return (
    <div
      className={cn(
        'border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-all bg-card',
        isDragOver ? 'border-primary bg-primary/5' : 'border-border',
        disabled && 'opacity-50 cursor-not-allowed'
      )}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={handleClick}
    >
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ALLOWED_FILE_TYPES.join(',')}
        onChange={handleFileChange}
        className="hidden"
      />
      <div className="flex flex-col items-center gap-2">
        <Upload className="h-10 w-10 text-muted-foreground" />
        <p className="text-sm font-medium text-foreground">
          {isDragOver ? 'Drop files here' : 'Drag & drop files or click to browse'}
        </p>
        <p className="text-xs text-muted-foreground">
          Supported: JPEG, PNG, TIFF, PDF (max 50MB each)
        </p>
      </div>
    </div>
  )
}
