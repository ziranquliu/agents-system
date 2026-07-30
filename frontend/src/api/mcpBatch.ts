import apiFetch from './client'

export interface MCPAgentBinding {
  id: string; mcp_server_id: string; mcp_server_name: string | null
  agent_id: string; agent_name: string | null; sync_mode: string
  override_config: string | null; override_protocol: string | null
  template_id: string | null; status: string
  source_version: string | null; synced_version: string | null
  is_encrypted: boolean; last_synced_at: string | null; sync_error: string | null
  created_at: string | null; updated_at: string | null
}

// 批量安装
export async function createMCPBatchInstall(mcpIds: string[], agentIds: string[], syncMode = 'shared', createdBy = '') {
  const resp = await apiFetch('/api/v1/mcp-batch/install', {
    method: 'POST', data: { mcp_ids: mcpIds, agent_ids: agentIds, sync_mode: syncMode, created_by: createdBy },
  })
  return resp.data
}

export async function executeMCPBatch(queueId: string) {
  const resp = await apiFetch(`/api/v1/mcp-batch/install/${queueId}/execute`, { method: 'POST' })
  return resp.data
}

export async function listMCPBatchQueues(offset = 0, limit = 20) {
  const resp = await apiFetch(`/api/v1/mcp-batch/install?offset=${offset}&limit=${limit}`, { method: 'GET' })
  return resp.data
}

export async function getMCPBatchQueue(queueId: string) {
  const resp = await apiFetch(`/api/v1/mcp-batch/install/${queueId}`, { method: 'GET' })
  return resp.data
}

// 绑定管理
export async function listMCPBindings(params: Record<string, string | number | undefined> = {}) {
  const qs = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => { if (v != null) qs.set(k, String(v)) })
  const resp = await apiFetch(`/api/v1/mcp-batch/bindings?${qs}`, { method: 'GET' })
  return resp.data
}

export async function updateMCPBinding(bindingId: string, data: Record<string, unknown>) {
  const resp = await apiFetch(`/api/v1/mcp-batch/bindings/${bindingId}`, { method: 'PUT', data })
  return resp.data
}

export async function removeMCPBinding(bindingId: string) {
  await apiFetch(`/api/v1/mcp-batch/bindings/${bindingId}`, { method: 'DELETE' })
}

// 同步
export async function checkMCPUpdates(mcpServerId: string) {
  const resp = await apiFetch(`/api/v1/mcp-batch/check-updates/${mcpServerId}`, { method: 'GET' })
  return resp.data
}

export async function syncMCPBinding(bindingId: string) {
  const resp = await apiFetch(`/api/v1/mcp-batch/sync/${bindingId}`, { method: 'POST' })
  return resp.data
}

export async function syncAllMCPBindings(mcpServerId: string) {
  const resp = await apiFetch(`/api/v1/mcp-batch/sync-all/${mcpServerId}`, { method: 'POST' })
  return resp.data
}
