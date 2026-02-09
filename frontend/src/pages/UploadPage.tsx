// File upload + config

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import DropZone from '../components/upload/DropZone'
import FileList from '../components/upload/FileList'
import UploadConfig from '../components/upload/UploadConfig'
import UploadProgress from '../components/upload/UploadProgress'
import { useUpload } from '../hooks/useUpload'
import { UploadConfig as Config } from '../types'

export default function UploadPage() {
  const navigate = useNavigate()
  const { files, uploading, progress, error, addFiles, removeFile, upload } = useUpload()
  const [config, setConfig] = useState<Config>({
    method: 'text_raw',
    tier: 0,
    output_format: 'txt',
    retention_hours: 168,
  })

  const handleUpload = async () => {
    const response = await upload(config)
    if (response) {
      navigate(`/batches/${response.request_id}`)
    }
  }

  return (
    <div className="upload-page">
      <div className="upload-page-header">
        <h1>OCR & Data Extraction</h1>
        <p className="upload-page-subtitle">
          Configure your extraction parameters and upload documents for processing.
        </p>
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="upload-page-grid">
        <div className="upload-page-main">
          <DropZone onFilesSelected={addFiles} disabled={uploading} />

          {files.length > 0 && (
            <>
              <FileList files={files} onRemove={removeFile} />
              <UploadProgress progress={progress} uploading={uploading} />
            </>
          )}
        </div>

        <div className="upload-page-sidebar">
          <UploadConfig config={config} onChange={setConfig} fileCount={files.length} />

          <button
            className="upload-submit-btn primary"
            onClick={handleUpload}
            disabled={files.length === 0 || uploading}
          >
            {uploading ? 'Uploading...' : 'Submit Request'}
          </button>
        </div>
      </div>
    </div>
  )
}
