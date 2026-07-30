import apiFetch from './client'

export async function getSystemHealth(): Promise<any> {
  const resp = await apiFetch('/api/v1/system/health', { method: 'GET' })
  return resp.data
}

export async function getApiLatency(): Promise<any> {
  const resp = await apiFetch('/api/v1/system/latency', { method: 'GET' })
  return resp.data
}

export async function createBackup(notes?: string): Promise<any> {
  const resp = await apiFetch('/api/v1/backup/create', { method: 'POST', data: { notes } })
  return resp.data
}

export async function listBackups(): Promise<any> {
  const resp = await apiFetch('/api/v1/backup/list', { method: 'GET' })
  return resp.data
}

export async function deleteBackup(backupId: string): Promise<any> {
  const resp = await apiFetch(`/api/v1/backup/${backupId}`, { method: 'DELETE' })
  return resp.data
}
