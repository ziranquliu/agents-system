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

export interface UpdateSnapshot {
  id: string
  component_type: string
  component_id: string
  component_name: string | null
  old_version: string | null
  new_version: string | null
  rolled_back: boolean
  rollback_time: string | null
  created_at: string | null
  created_by: string | null
}

export interface UpdateLogItem {
  id: string
  component_type: string
  component_id: string
  component_name: string | null
  action: string
  old_version: string | null
  new_version: string | null
  compatibility: string
  status: string
  detail: string | null
  created_at: string | null
  created_by: string | null
}

export async function batchApplyUpdates(componentType: string, componentIds: string[]): Promise<any> {
  const resp = await apiFetch('/api/v1/updates/batch', { method: 'POST', data: { component_type: componentType, component_ids: componentIds } })
  return resp.data
}

export async function listUpdateSnapshots(componentType?: string, limit = 50): Promise<UpdateSnapshot[]> {
  const qs = new URLSearchParams({ limit: String(limit) })
  if (componentType) qs.set('component_type', componentType)
  const resp = await apiFetch(`/api/v1/updates/snapshots?${qs}`, { method: 'GET' })
  return resp.data
}

export async function rollbackUpdate(snapshotId: string): Promise<any> {
  const resp = await apiFetch(`/api/v1/updates/rollback/${snapshotId}`, { method: 'POST' })
  return resp.data
}

export async function listUpdateLogs(componentType?: string, limit = 50): Promise<UpdateLogItem[]> {
  const qs = new URLSearchParams({ limit: String(limit) })
  if (componentType) qs.set('component_type', componentType)
  const resp = await apiFetch(`/api/v1/updates/logs?${qs}`, { method: 'GET' })
  return resp.data
}
