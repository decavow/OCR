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

// =============================================================================
// Admin Dashboard API
// =============================================================================

export interface AdminStats {
  total_users: number
  total_requests: number
  total_jobs: number
  completed_jobs: number
  failed_jobs: number
  processing_jobs: number
  avg_processing_time_ms: number | null
  success_rate: number
}

export interface AdminRequestItem {
  id: string
  user_id: string
  user_email: string
  method: string
  tier: number
  output_format: string
  status: string
  total_files: number
  completed_files: number
  failed_files: number
  created_at: string
  completed_at: string | null
}

export interface AdminRequestListResponse {
  items: AdminRequestItem[]
  total: number
  page: number
  page_size: number
}

export interface AdminUserItem {
  id: string
  email: string
  is_admin: boolean
  created_at: string
  total_requests: number
}

export interface AdminUserListResponse {
  items: AdminUserItem[]
  total: number
}

export interface JobVolumePoint {
  hour: string
  volume: number
  avg_latency_ms: number
}

export interface JobVolumeResponse {
  data: JobVolumePoint[]
}

export interface AdminServiceInstance {
  id: string
  service_type_id: string
  status: string
  registered_at: string
  last_heartbeat_at: string
  current_job_id: string | null
}

export interface AdminServiceInstanceListResponse {
  items: AdminServiceInstance[]
  total: number
}

export async function getAdminStats(): Promise<AdminStats> {
  const response = await client.get<AdminStats>('/admin/dashboard/stats')
  return response.data
}

export async function getAdminRecentRequests(
  page = 1,
  pageSize = 20,
): Promise<AdminRequestListResponse> {
  const response = await client.get<AdminRequestListResponse>(
    '/admin/dashboard/recent-requests',
    { params: { page, page_size: pageSize } },
  )
  return response.data
}

export async function getAdminUsers(
  page = 1,
  pageSize = 50,
): Promise<AdminUserListResponse> {
  const response = await client.get<AdminUserListResponse>(
    '/admin/dashboard/users',
    { params: { page, page_size: pageSize } },
  )
  return response.data
}

export async function getAdminJobVolume(hours = 24): Promise<JobVolumeResponse> {
  const response = await client.get<JobVolumeResponse>(
    '/admin/dashboard/job-volume',
    { params: { hours } },
  )
  return response.data
}

export async function getAdminServiceInstances(
  typeId?: string,
  status?: string,
): Promise<AdminServiceInstanceListResponse> {
  const params: Record<string, string> = {}
  if (typeId) params.type_id = typeId
  if (status) params.status = status
  const response = await client.get<AdminServiceInstanceListResponse>(
    '/admin/dashboard/service-instances',
    { params },
  )
  return response.data
}
