// File types

export interface FileInfo {
  id: string
  request_id: string
  original_name: string
  mime_type: string
  size_bytes: number
  page_count: number
  object_key: string
  created_at: string
}

export interface UploadFile {
  file: File
  id: string
  progress: number
  status: 'pending' | 'uploading' | 'completed' | 'error'
  error?: string
}

export interface UploadConfig {
  method: string
  tier: number
  output_format: 'txt' | 'json' | 'md'
  retention_hours: number
}

export interface PresignedUrlResponse {
  url: string
  expires_at: string
}
