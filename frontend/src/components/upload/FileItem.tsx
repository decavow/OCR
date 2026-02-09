import { UploadFile } from '../../types'

// Single file row (name, size, type, status)
interface FileItemProps {
  file: UploadFile
  onRemove: () => void
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function FileItem({ file, onRemove }: FileItemProps) {
  const statusClass = `status-${file.status}`

  return (
    <div className={`file-item ${statusClass}`}>
      <div className="file-info">
        <span className="file-name">{file.file.name}</span>
        <span className="file-size">{formatFileSize(file.file.size)}</span>
        <span className="file-type">{file.file.type || 'Unknown'}</span>
      </div>

      <div className="file-status">
        {file.status === 'pending' && <span className="status-badge pending">Pending</span>}
        {file.status === 'uploading' && (
          <span className="status-badge uploading">Uploading...</span>
        )}
        {file.status === 'completed' && (
          <span className="status-badge completed">Uploaded</span>
        )}
        {file.status === 'error' && (
          <span className="status-badge error" title={file.error}>
            Error
          </span>
        )}
      </div>

      {file.status === 'pending' && (
        <button className="remove-btn" onClick={onRemove} title="Remove file">
          x
        </button>
      )}
    </div>
  )
}
