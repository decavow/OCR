// Upload progress bar

interface UploadProgressProps {
  progress: number
  uploading: boolean
}

export default function UploadProgress({ progress, uploading }: UploadProgressProps) {
  if (!uploading) return null

  return (
    <div className="upload-progress">
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${progress}%` }} />
      </div>
      <span className="progress-text">{progress}%</span>
    </div>
  )
}
