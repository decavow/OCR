// "Extracted Text Result" header bar: download TXT, download JSON, Copy button

interface ResultToolbarProps {
  fileId: string
}

export default function ResultToolbar({ fileId }: ResultToolbarProps) {
  const handleDownloadTxt = () => {
    window.open(`/api/v1/files/${fileId}/download?format=txt`, '_blank')
  }

  const handleDownloadJson = () => {
    window.open(`/api/v1/files/${fileId}/download?format=json`, '_blank')
  }

  const handleCopy = () => {
    // Copy handled by parent component
  }

  return (
    <div className="result-toolbar">
      <span>Extracted Text Result</span>
      <div className="toolbar-actions">
        <button onClick={handleDownloadTxt}>TXT</button>
        <button onClick={handleDownloadJson}>JSON</button>
        <button onClick={handleCopy}>Copy</button>
      </div>
    </div>
  )
}
