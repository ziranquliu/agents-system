import apiFetch from './client'

export interface OperationLog {
  id: string
  user_id: string
  action: string
  resource_type: string
  resource_id: string | null
  detail: string | null
  ip_address: string | null
  user_agent: string | null
  created_at: string
}

export interface ListOperationLogsParams {
  page?: number
  page_size?: number
  action?: string
  resource_type?: string
  user_id?: string
  date_from?: string
  date_to?: string
}

export interface ListOperationLogsResponse {
  total: number
  page: number
  page_size: number
  items: OperationLog[]
}

export async function listOperationLogs(params: ListOperationLogsParams = {}): Promise<ListOperationLogsResponse> {
  const qs = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') {
      qs.set(k, String(v))
    }
  })
  const query = qs.toString()
  const resp = await apiFetch(`/api/v1/operation-logs${query ? `?${query}` : ''}`, { method: 'GET' })
  return resp.data
}

export async function listOperationActions(): Promise<string[]> {
  const resp = await apiFetch('/api/v1/operation-logs/actions', { method: 'GET' })
  return resp.data.actions
}

export async function listResourceTypes(): Promise<string[]> {
  const resp = await apiFetch('/api/v1/operation-logs/resource-types', { method: 'GET' })
  return resp.data.resource_types
}
