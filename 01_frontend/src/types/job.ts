// Job types

export type JobStatus =
  | 'SUBMITTED'
  | 'VALIDATING'
  | 'QUEUED'
  | 'PROCESSING'
  | 'COMPLETED'
  | 'PARTIAL_SUCCESS'
  | 'FAILED'
  | 'REJECTED'
  | 'CANCELLED'
  | 'DEAD_LETTER'

export interface Job {
  id: string
  request_id: string
  file_id: string
  status: JobStatus
  method: string
  tier: number
  output_format: string
  retry_count: number
  max_retries: number
  error_history: ErrorEntry[]
  started_at: string | null
  completed_at: string | null
  processing_time_ms: number | null
  result_path: string | null
  worker_id: string | null
  created_at: string
}

export interface ErrorEntry {
  error: string
  retriable: boolean
  timestamp: string
}

export interface JobResult {
  text: string
  lines: number
  metadata: JobResultMetadata
}

export interface JobResultMetadata {
  method: string
  tier: string
  processing_time_ms: number
  service_version: string
  engine_name: string | null
}
