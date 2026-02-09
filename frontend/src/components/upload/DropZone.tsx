// Drag-drop area with file picker

import { useRef, useState, DragEvent, ChangeEvent } from 'react'
import { ALLOWED_FILE_TYPES } from '../../config'

interface DropZoneProps {
  onFilesSelected: (files: File[]) => void
  disabled?: boolean
}

export default function DropZone({ onFilesSelected, disabled }: DropZoneProps) {
  const [isDragOver, setIsDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleDragOver = (e: DragEvent) => {
    e.preventDefault()
    if (!disabled) {
      setIsDragOver(true)
    }
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
    if (validFiles.length > 0) {
      onFilesSelected(validFiles)
    }
  }

  const handleClick = () => {
    if (!disabled) {
      inputRef.current?.click()
    }
  }

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      onFilesSelected(Array.from(e.target.files))
      e.target.value = ''
    }
  }

  return (
    <div
      className={`drop-zone ${isDragOver ? 'drag-over' : ''} ${disabled ? 'disabled' : ''}`}
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
        style={{ display: 'none' }}
      />
      <div className="drop-zone-content">
        <p className="drop-zone-title">
          {isDragOver ? 'Drop files here' : 'Drag & drop files or click to browse'}
        </p>
        <p className="drop-zone-hint">
          Supported: JPEG, PNG, TIFF, PDF (max 50MB each)
        </p>
      </div>
    </div>
  )
}
