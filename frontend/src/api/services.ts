import client from './client'

export interface AvailableService {
  id: string
  display_name: string
  description: string | null
  allowed_methods: string[]
  allowed_tiers: number[]
  active_instances: number
}

export interface AvailableServicesResponse {
  items: AvailableService[]
  total: number
}

export async function getAvailableServices(): Promise<AvailableServicesResponse> {
  const response = await client.get<AvailableServicesResponse>('/services/available')
  return response.data
}
