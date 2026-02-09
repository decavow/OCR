import { useState } from 'react'
import { UploadFile, UploadConfig } from '../types'
import { uploadFiles, UploadResponse } from '../api/upload'

// File upload with progress tracking
export function useUpload() {
  const [files, setFiles] = useState<UploadFile[]>([])
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)

  const addFiles = (newFiles: File[]) => {
    const uploadFiles: UploadFile[] = newFiles.map((file) => ({
      file,
      id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      progress: 0,
      status: 'pending' as const,
    }))
    setFiles((prev) => [...prev, ...uploadFiles])
    setError(null)
  }

  const removeFile = (id: string) => {
    setFiles((prev) => prev.filter((f) => f.id !== id))
  }

  const upload = async (config: UploadConfig): Promise<UploadResponse | null> => {
    if (files.length === 0) return null

    setUploading(true)
    setProgress(0)
    setError(null)

    // Update all files to uploading status
    setFiles((prev) =>
      prev.map((f) => ({ ...f, status: 'uploading' as const }))
    )

    try {
      const rawFiles = files.map((f) => f.file)
      const response = await uploadFiles(rawFiles, config, setProgress)

      // Update all files to completed
      setFiles((prev) =>
        prev.map((f) => ({ ...f, status: 'completed' as const, progress: 100 }))
      )

      return response
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Upload failed'
      setError(message)

      // Update all files to error
      setFiles((prev) =>
        prev.map((f) => ({ ...f, status: 'error' as const, error: message }))
      )
      return null
    } finally {
      setUploading(false)
    }
  }

  const reset = () => {
    setFiles([])
    setProgress(0)
    setError(null)
    setUploading(false)
  }

  return {
    files,
    uploading,
    progress,
    error,
    addFiles,
    removeFile,
    upload,
    reset,
  }
}
