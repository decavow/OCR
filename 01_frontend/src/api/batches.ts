import client from './client'
import { Batch, BatchListResponse, Job } from '../types'

export interface BatchDetail extends Batch {
  jobs: Job[]
}

export interface BatchFilters {
  status?: string
  method?: string
  date_from?: string
  date_to?: string
}

export async function getBatches(page = 1, pageSize = 20, filters?: BatchFilters): Promise<BatchListResponse> {
  const params: Record<string, string | number> = { page, page_size: pageSize }
  if (filters?.status) params.status = filters.status
  if (filters?.method) params.method = filters.method
  if (filters?.date_from) params.date_from = filters.date_from
  if (filters?.date_to) params.date_to = filters.date_to
  const response = await client.get<BatchListResponse>('/requests', { params })
  return response.data
}

export async function getBatch(id: string): Promise<BatchDetail> {
  const response = await client.get<BatchDetail>(`/requests/${id}`)
  return response.data
}

export interface CancelResponse {
  success: boolean
  cancelled_jobs: number
  message: string
}

export async function cancelBatch(id: string): Promise<CancelResponse> {
  const response = await client.post<CancelResponse>(`/requests/${id}/cancel`)
  return response.data
}
