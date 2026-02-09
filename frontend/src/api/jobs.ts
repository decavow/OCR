import client from './client'
import { Job, JobResult } from '../types'

export async function getJob(id: string): Promise<Job> {
  const response = await client.get<Job>(`/jobs/${id}`)
  return response.data
}

export async function getJobResult(id: string, format = 'text'): Promise<JobResult> {
  const response = await client.get<JobResult>(`/jobs/${id}/result`, {
    params: { format },
  })
  return response.data
}

export function getJobDownloadUrl(id: string): string {
  return `${client.defaults.baseURL}/jobs/${id}/download`
}
