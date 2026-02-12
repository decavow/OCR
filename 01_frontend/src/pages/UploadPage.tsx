import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import DropZone from '../components/upload/DropZone'
import FileList from '../components/upload/FileList'
import UploadConfig from '../components/upload/UploadConfig'
import UploadProgress from '../components/upload/UploadProgress'
import { useUpload } from '../hooks/useUpload'
import { UploadConfig as Config } from '../types'
import { Button as ShadcnButton } from '@/components/ui/button'

export default function UploadPage() {
  const navigate = useNavigate()
  const { files, uploading, progress, error, addFiles, removeFile, upload } = useUpload()
  const [config, setConfig] = useState<Config>({
    method: 'text_raw',
    tier: 0,
    output_format: 'txt',
    retention_hours: 168,
  })
  const [servicesAvailable, setServicesAvailable] = useState(false)

  const handleUpload = async () => {
    const response = await upload(config)
    if (response) {
      navigate(`/batches/${response.request_id}`)
    }
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground">OCR & Data Extraction</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Configure your extraction parameters and upload documents for processing.
        </p>
      </div>

      {error && (
        <div className="text-sm text-destructive bg-destructive/10 border border-destructive/30 rounded-md p-3 mb-4">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-6 items-start">
        <div className="space-y-4">
          <DropZone onFilesSelected={addFiles} disabled={uploading} />
          {files.length > 0 && (
            <>
              <FileList files={files} onRemove={removeFile} />
              <UploadProgress progress={progress} uploading={uploading} />
            </>
          )}
        </div>

        <div className="space-y-4">
          <UploadConfig config={config} onChange={setConfig} fileCount={files.length} onServicesLoaded={setServicesAvailable} />
          <ShadcnButton
            className="w-full"
            size="lg"
            onClick={handleUpload}
            disabled={files.length === 0 || uploading || !servicesAvailable}
          >
            {uploading ? 'Uploading...' : 'Submit Request'}
          </ShadcnButton>
        </div>
      </div>
    </div>
  )
}
