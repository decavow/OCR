interface OriginalPreviewProps {
  fileId: string
}

export default function OriginalPreview({ fileId }: OriginalPreviewProps) {
  const previewUrl = `/api/v1/files/${fileId}/original-url`

  return (
    <div className="flex-1 flex items-center justify-center p-4 overflow-auto">
      <img src={previewUrl} alt="Original file preview" className="max-w-full max-h-full object-contain" />
    </div>
  )
}
