import apiFetch from './client'

export interface ModelTemplateVersion {
  id: string
  template_id: string
  version: number
  change_log: string
  name: string
  provider: string
  model: string
  config: Record<string, unknown>
  description: string
  created_by: string
  created_at: string | null
}

export interface ModelTemplateBinding {
  id: string
  template_id: string
  agent_id: string
  override_config: Record<string, unknown>
  override_model: string | null
  override_provider: string | null
  sync_mode: string
  gray_percentage: number
  gray_status: string
  gray_synced_version: number | null
  gray_error: string | null
  last_synced_at: string | null
  created_at: string | null
  updated_at: string | null
}

export interface TemplateDetail {
  id: string
  name: string
  provider: string
  model: string
  config: Record<string, unknown>
  description: string
  is_default: boolean
  workspace_id: string | null
  created_by: string | null
  created_at: string | null
  updated_at: string | null
  binding_count: number
  version_count: number
  bindings: ModelTemplateBinding[]
}

// 创建版本
export async function createTemplateVersion(templateId: string, changeLog = '', userId = ''): Promise<ModelTemplateVersion> {
  const resp = await apiFetch(`/api/v1/model-templates/${templateId}/versions`, {
    method: 'POST',
    data: { change_log: changeLog, user_id: userId },
  })
  return resp.data
}

// 版本列表
export async function listTemplateVersions(templateId: string, offset = 0, limit = 20): Promise<{ data: ModelTemplateVersion[]; total: number }> {
  const resp = await apiFetch(`/api/v1/model-templates/${templateId}/versions?offset=${offset}&limit=${limit}`, { method: 'GET' })
  return resp.data
}

// 回滚模板
export async function rollbackTemplate(templateId: string, versionId: string, userId = ''): Promise<void> {
  await apiFetch(`/api/v1/model-templates/${templateId}/rollback`, {
    method: 'POST',
    data: { version_id: versionId, user_id: userId },
  })
}

// 绑定智能体
export async function bindAgentToTemplate(templateId: string, agentId: string, overrideConfig?: Record<string, unknown>, syncMode = 'auto', grayPercentage = 100): Promise<ModelTemplateBinding> {
  const resp = await apiFetch(`/api/v1/model-templates/${templateId}/bindings`, {
    method: 'POST',
    data: { agent_id: agentId, override_config: overrideConfig, sync_mode: syncMode, gray_percentage: grayPercentage },
  })
  return resp.data
}

// 解除绑定
export async function unbindAgentFromTemplate(templateId: string, agentId: string): Promise<void> {
  await apiFetch(`/api/v1/model-templates/${templateId}/bindings/${agentId}`, { method: 'DELETE' })
}

// 查询绑定列表
export async function listTemplateBindings(templateId: string, status?: string, offset = 0, limit = 50): Promise<{ data: ModelTemplateBinding[]; total: number }> {
  let url = `/api/v1/model-templates/${templateId}/bindings?offset=${offset}&limit=${limit}`
  if (status) url += `&status=${status}`
  const resp = await apiFetch(url, { method: 'GET' })
  return resp.data
}

// 更新绑定
export async function updateBinding(bindingId: string, data: Record<string, unknown>): Promise<ModelTemplateBinding> {
  const resp = await apiFetch(`/api/v1/model-templates/bindings/${bindingId}`, { method: 'PUT', data })
  return resp.data
}

// 同步模板到智能体
export async function syncTemplateToAgents(templateId: string, forceAll = false): Promise<{ synced: number; skipped: number; failed: number }> {
  const resp = await apiFetch(`/api/v1/model-templates/${templateId}/sync`, {
    method: 'POST',
    data: { force_all: forceAll },
  })
  return resp.data
}

// 回滚绑定
export async function rollbackBindings(templateId: string, targetVersion: number): Promise<{ rolled_back: number; target_version: number }> {
  const resp = await apiFetch(`/api/v1/model-templates/${templateId}/rollback-bindings`, {
    method: 'POST',
    data: { target_version: targetVersion },
  })
  return resp.data
}

// 获取模板详情（含绑定+版本）
export async function getTemplateDetail(templateId: string): Promise<TemplateDetail> {
  const resp = await apiFetch(`/api/v1/model-templates/${templateId}/detail`, { method: 'GET' })
  return resp.data
}
