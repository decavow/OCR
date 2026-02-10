import client from './client'
import { Batch, BatchListResponse, Job } from '../types'

export interface BatchDetail extends Batch {
  jobs: Job[]
}

export async function getBatches(page = 1, pageSize = 20): Promise<BatchListResponse> {
  const response = await client.get<BatchListResponse>('/requests', {
    params: { page, page_size: pageSize },
  })
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
