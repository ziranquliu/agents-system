import apiFetch from './client'

export interface UpdateItem {
  component_type: string
  component_id: string
  component_name: string
  current_version: string
  latest_version: string
  description: string | null
  icon: string | null
}

export async function getAvailableUpdates(): Promise<{ total: number; updates: UpdateItem[] }> {
  const resp = await apiFetch('/api/v1/updates/available', { method: 'GET' })
  return resp.data
}

export async function getUpdateCount(): Promise<{ count: number }> {
  const resp = await apiFetch('/api/v1/updates/count', { method: 'GET' })
  return resp.data
}

export async function refreshUpdates(): Promise<{ message: string; updates_count: number }> {
  const resp = await apiFetch('/api/v1/updates/refresh', { method: 'POST' })
  return resp.data
}

export async function applyUpdate(componentType: string, componentId: string): Promise<any> {
  const resp = await apiFetch(`/api/v1/updates/apply/${componentType}/${componentId}`, { method: 'POST' })
  return resp.data
}
