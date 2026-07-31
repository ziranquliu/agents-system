import apiFetch from './client'

export interface ScanSummary {
  checked: number
  healthy: number
  warning: number
  error: number
}

export interface ScanItem {
  id: string
  scan_id: string
  component_type: string
  component_id: string
  component_name: string | null
  status: string
  error_message: string | null
  details: Record<string, any> | null
  scanned_at: string | null
}

export interface ScanSession {
  id: string
  status: string
  summary: ScanSummary | null
  started_at: string | null
  completed_at: string | null
  triggered_by: string | null
}

export async function triggerScan(): Promise<{ message: string; scan_id: string }> {
  const resp = await apiFetch('/api/v1/scanner/trigger', { method: 'POST' })
  return resp.data
}

export async function getLatestScan(): Promise<{ scan: ScanSession | null }> {
  const resp = await apiFetch('/api/v1/scanner/latest', { method: 'GET' })
  return resp.data
}

export async function getScanHistory(page = 1, pageSize = 10): Promise<{ scans: ScanSession[]; total: number; page: number; page_size: number }> {
  const resp = await apiFetch(`/api/v1/scanner/history?page=${page}&page_size=${pageSize}`, { method: 'GET' })
  return resp.data
}

export async function getScanResults(scanId: string, componentType?: string, status?: string): Promise<{ items: ScanItem[] }> {
  const qs = new URLSearchParams()
  if (componentType) qs.set('component_type', componentType)
  if (status) qs.set('status', status)
  const resp = await apiFetch(`/api/v1/scanner/results/${scanId}${qs.toString() ? `?${qs}` : ''}`, { method: 'GET' })
  return resp.data
}

export async function cleanupOldScans(keepCount = 30): Promise<{ message: string; deleted: number; keep_count: number }> {
  const resp = await apiFetch(`/api/v1/scanner/cleanup?keep_count=${keepCount}`, { method: 'POST' })
  return resp.data
}

export interface ScanAlert {
  id: string
  component_type: string
  component_id: string
  component_name: string | null
  previous_status: string | null
  current_status: string
  severity: string
  message: string | null
  status: string
  created_at: string | null
}

export async function getScanAlerts(params?: { status?: string; severity?: string; component_type?: string; page?: number; page_size?: number }): Promise<{ total: number; page: number; page_size: number; items: ScanAlert[] }> {
  const qs = new URLSearchParams()
  if (params?.status) qs.set('status', params.status)
  if (params?.severity) qs.set('severity', params.severity)
  if (params?.component_type) qs.set('component_type', params.component_type)
  if (params?.page) qs.set('page', String(params.page))
  if (params?.page_size) qs.set('page_size', String(params.page_size))
  const resp = await apiFetch(`/api/v1/scanner/alerts${qs.toString() ? `?${qs}` : ''}`, { method: 'GET' })
  return resp.data
}

export async function updateScanAlert(alertId: string, status: string): Promise<{ id: string; status: string }> {
  const resp = await apiFetch(`/api/v1/scanner/alerts/${alertId}`, { method: 'PATCH', data: { status } })
  return resp.data
}
