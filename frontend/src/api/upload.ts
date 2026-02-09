import client from './client'
import { UploadConfig } from '../types'

export interface UploadFileInfo {
  id: string
  original_name: string
  mime_type: string
  size_bytes: number
}

export interface UploadResponse {
  request_id: string
  status: string
  total_files: number
  output_format: string
  method: string
  tier: number
  created_at: string
  files: UploadFileInfo[]
}

export async function uploadFiles(
  files: File[],
  config: UploadConfig,
  onProgress?: (progress: number) => void
): Promise<UploadResponse> {
  const formData = new FormData()

  // Add files
  files.forEach((file) => {
    formData.append('files', file)
  })

  // Build query params
  const params = new URLSearchParams({
    output_format: config.output_format,
    retention_hours: config.retention_hours.toString(),
    method: config.method,
    tier: config.tier.toString(),
  })

  const response = await client.post<UploadResponse>(
    `/upload?${params.toString()}`,
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          onProgress(percent)
        }
      },
    }
  )

  return response.data
}
