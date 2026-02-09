// Left panel: image/PDF preview of source file
// Loads original from MinIO via presigned URL

interface OriginalPreviewProps {
  fileId: string
}

export default function OriginalPreview({ fileId }: OriginalPreviewProps) {
  // TODO: Fetch presigned URL from API
  const previewUrl = `/api/v1/files/${fileId}/original-url`

  return (
    <div className="original-preview">
      <img src={previewUrl} alt="Original file preview" />
    </div>
  )
}
