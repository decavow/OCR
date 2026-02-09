import client from './client'
import { FileInfo, PresignedUrlResponse } from '../types'

export async function getFile(id: string): Promise<FileInfo> {
  const response = await client.get<FileInfo>(`/files/${id}`)
  return response.data
}

export async function getOriginalUrl(id: string): Promise<PresignedUrlResponse> {
  const response = await client.get<PresignedUrlResponse>(`/files/${id}/original-url`)
  return response.data
}

export async function getResultUrl(id: string): Promise<PresignedUrlResponse> {
  const response = await client.get<PresignedUrlResponse>(`/files/${id}/result-url`)
  return response.data
}

export async function downloadFile(id: string, type: 'original' | 'result' = 'result'): Promise<Blob> {
  const response = await client.get(`/files/${id}/download`, {
    params: { type },
    responseType: 'blob',
  })
  return response.data
}
