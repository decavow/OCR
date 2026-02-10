import client from './client'

export interface ServiceTypeInstanceCount {
  [status: string]: number
}

export interface ServiceType {
  id: string
  display_name: string
  description: string | null
  status: string
  access_key: string | null
  allowed_methods: string[]
  allowed_tiers: number[]
  engine_info: Record<string, unknown> | null
  dev_contact: string | null
  max_instances: number
  registered_at: string
  approved_at: string | null
  approved_by: string | null
  rejected_at: string | null
  rejection_reason: string | null
  instance_count: ServiceTypeInstanceCount
}

export interface ServiceTypeListResponse {
  items: ServiceType[]
  total: number
}

export async function getServiceTypes(status?: string): Promise<ServiceTypeListResponse> {
  const params = status ? { status } : {}
  const response = await client.get<ServiceTypeListResponse>('/admin/service-types', { params })
  return response.data
}

export async function approveServiceType(typeId: string): Promise<ServiceType> {
  const response = await client.post<ServiceType>(`/admin/service-types/${typeId}/approve`)
  return response.data
}

export async function rejectServiceType(typeId: string, reason: string): Promise<ServiceType> {
  const response = await client.post<ServiceType>(`/admin/service-types/${typeId}/reject`, { reason })
  return response.data
}

export async function disableServiceType(typeId: string): Promise<ServiceType> {
  const response = await client.post<ServiceType>(`/admin/service-types/${typeId}/disable`)
  return response.data
}

export async function enableServiceType(typeId: string): Promise<ServiceType> {
  const response = await client.post<ServiceType>(`/admin/service-types/${typeId}/enable`)
  return response.data
}

export async function deleteServiceType(typeId: string): Promise<void> {
  await client.delete(`/admin/service-types/${typeId}`)
}
