// Batch types (maps to Request in backend)

export type BatchStatus =
  | 'PROCESSING'
  | 'COMPLETED'
  | 'PARTIAL_SUCCESS'
  | 'FAILED'
  | 'CANCELLED'

export interface Batch {
  id: string
  user_id: string
  method: string
  tier: number
  output_format: string
  retention_hours: number
  status: BatchStatus
  total_files: number
  completed_files: number
  failed_files: number
  created_at: string
  completed_at: string | null
}

export interface BatchListResponse {
  items: Batch[]
  total: number
  page: number
  page_size: number
}
