import client from './client'

/** 模型配置模板 */
export interface ModelConfigInfo {
  id: string
  name: string
  provider: string
  model_name: string
  endpoint: string | null
  api_key_masked: string | null
  temperature: number | null
  max_tokens: number | null
  context_window: number | null
  embedding_model: string | null
  is_default: boolean
  description: string | null
  created_by: string
  created_at: string
  updated_at: string | null
}

export interface ModelConfigListResponse {
  items: ModelConfigInfo[]
  total: number
  page: number
  page_size: number
}

export interface ModelConfigCreatePayload {
  name: string
  provider: string
  model_name: string
  endpoint?: string | null
  api_key?: string | null
  temperature?: number | null
  max_tokens?: number | null
  context_window?: number | null
  embedding_model?: string | null
  is_default?: boolean
  description?: string | null
}

export interface ModelConfigUpdatePayload {
  name?: string
  provider?: string
  model_name?: string
  endpoint?: string | null
  api_key?: string | null
  temperature?: number | null
  max_tokens?: number | null
  context_window?: number | null
  embedding_model?: string | null
  is_default?: boolean | null
  description?: string | null
}

export interface ModelTestResponse {
  success: boolean
  response?: string | null
  model?: string | null
  latency_ms?: number | null
  error?: string | null
}

/** 支持的 Provider */
export const PROVIDERS = [
  { value: '', label: '全部 Provider' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'ollama', label: 'Ollama' },
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'glm', label: 'GLM (智谱)' },
  { value: 'qwen', label: 'Qwen (通义千问)' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'azure', label: 'Azure OpenAI' },
]

/** 获取模型配置列表 */
export async function listModelConfigs(params?: {
  page?: number
  page_size?: number
  provider?: string
  search?: string
}) {
  const { data } = await client.get<ModelConfigListResponse>('/models/', { params })
  return data
}

/** 获取单个配置 */
export async function getModelConfig(id: string) {
  const { data } = await client.get<ModelConfigInfo>(`/models/${id}`)
  return data
}

/** 创建配置 */
export async function createModelConfig(payload: ModelConfigCreatePayload) {
  const { data } = await client.post<ModelConfigInfo>('/models/', payload)
  return data
}

/** 更新配置 */
export async function updateModelConfig(id: string, payload: ModelConfigUpdatePayload) {
  const { data } = await client.put<ModelConfigInfo>(`/models/${id}`, payload)
  return data
}

/** 删除配置 */
export async function deleteModelConfig(id: string) {
  await client.delete(`/models/${id}`)
}

/** 测试模型连接 */
export async function testModelConnection(id: string) {
  const { data } = await client.post<ModelTestResponse>(`/models/${id}/test`)
  return data
}

/* ==================== 模型模板版本 / 绑定 ==================== */

export interface ModelVersionInfo {
  id: string
  template_id: string
  version: number
  name: string
  provider: string
  model: string
  config: string
  change_log: string | null
  created_by: string
  created_at: string
}

export interface ModelBindingInfo {
  id: string
  template_id: string
  agent_id: string
  sync_mode: string
  override_config: string
  gray_percentage: number
  gray_status: string
  last_synced_at: string | null
  agent_name?: string | null
  agent_status?: string | null
  binding_status: string
}

/** 获取模板版本历史 */
export async function listModelVersions(templateId: string) {
  const { data } = await client.get<{ items: ModelVersionInfo[]; total: number }>(
    `/models/${templateId}/versions`
  )
  return data
}

/** 回滚到指定版本 */
export async function rollbackModelVersion(templateId: string, targetVersion: number) {
  const { data } = await client.post(`/models/${templateId}/rollback`, {
    target_version: targetVersion,
  })
  return data
}

/** 获取绑定Agent列表 */
export async function listModelBindings(templateId: string) {
  const { data } = await client.get<{ items: ModelBindingInfo[]; total: number }>(
    `/models/${templateId}/bound-agents`
  )
  return data
}

/** 同步模板到所有绑定Agent */
export async function syncModelTemplate(templateId: string) {
  const { data } = await client.post(`/models/${templateId}/sync`)
  return data
}

/** 删除指定版本 */
export async function deleteModelVersion(templateId: string, version: number) {
  const { data } = await client.delete(`/models/${templateId}/versions/${version}`)
  return data
}
