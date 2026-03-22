import { useState, useEffect } from 'react'
import { previewOriginal } from '../../api/files'

interface OriginalPreviewProps {
  fileId: string
}

export default function OriginalPreview({ fileId }: OriginalPreviewProps) {
  const [imageUrl, setImageUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let objectUrl: string | null = null
    const fetchPreview = async () => {
      try {
        const blob = await previewOriginal(fileId)
        objectUrl = URL.createObjectURL(blob)
        setImageUrl(objectUrl)
      } catch {
        setError('Failed to load preview')
      }
    }
    fetchPreview()
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [fileId])

  return (
    <div className="flex-1 flex items-center justify-center p-4 overflow-auto">
      {error && <p className="text-sm text-destructive">{error}</p>}
      {imageUrl && (
        <img src={imageUrl} alt="Original file preview" className="max-w-full max-h-full object-contain" />
      )}
    </div>
  )
}
