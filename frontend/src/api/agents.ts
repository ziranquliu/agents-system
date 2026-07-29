import client from './client'

export interface AgentInfo {
  id: string
  name: string
  description: string | null
  avatar: string | null
  status: string
  model_provider: string | null
  model_name: string | null
  model_config_template_id: string | null
  temperature: number | null
  max_tokens: number | null
  context_window: number | null
  system_prompt: string | null
  welcome_message: string | null
  enabled_skills: string | null
  enabled_mcp_servers: string | null
  workspace_id: string | null
  created_by: string
  created_at: string
  updated_at: string | null
}

export interface AgentListResponse {
  items: AgentInfo[]
  total: number
  page: number
  page_size: number
}

export interface AgentCreatePayload {
  name: string
  description?: string | null
  avatar?: string | null
  system_prompt?: string | null
  welcome_message?: string | null
  model_provider?: string | null
  model_name?: string | null
  model_config_template_id?: string | null
  temperature?: number | null
  max_tokens?: number | null
  context_window?: number | null
  enabled_skills?: string[] | null
  enabled_mcp_servers?: string[] | null
  workspace_id?: string | null
  status?: string
}

export interface AgentUpdatePayload {
  name?: string
  description?: string | null
  avatar?: string | null
  system_prompt?: string | null
  welcome_message?: string | null
  model_provider?: string | null
  model_name?: string | null
  model_config_template_id?: string | null
  temperature?: number | null
  max_tokens?: number | null
  context_window?: number | null
  enabled_skills?: string[] | null
  enabled_mcp_servers?: string[] | null
}

/** 获取 Agent 列表（分页 + 筛选） */
export async function listAgents(params?: {
  page?: number
  page_size?: number
  status?: string
  search?: string
}) {
  const { data } = await client.get<AgentListResponse>('/agents/', { params })
  return data
}

/** 获取单个 Agent */
export async function getAgent(id: string) {
  const { data } = await client.get<AgentInfo>(`/agents/${id}`)
  return data
}

/** 创建 Agent */
export async function createAgent(payload: AgentCreatePayload) {
  const { data } = await client.post<AgentInfo>('/agents/', payload)
  return data
}

/** 更新 Agent */
export async function updateAgent(id: string, payload: AgentUpdatePayload) {
  const { data } = await client.put<AgentInfo>(`/agents/${id}`, payload)
  return data
}

/** 删除 Agent */
export async function deleteAgent(id: string) {
  await client.delete(`/agents/${id}`)
}

/** 更新 Agent 状态 */
export async function updateAgentStatus(id: string, status: string) {
  const { data } = await client.patch<AgentInfo>(`/agents/${id}/status`, {
    status,
  })
  return data
}

/* ── 本地 Agent 发现 ──────────────────────────────────── */

export interface DiscoveredModel {
  source: string
  source_name: string
  model_name: string
  provider: string
  size?: number
  endpoint: string
}

export interface DiscoverResponse {
  items: DiscoveredModel[]
  total: number
  message: string
}

/** 扫描本地 AI 服务，发现可用模型 */
export async function discoverAgents() {
  const { data } = await client.post<DiscoverResponse>('/discover/agents')
  return data
}

/** 将发现的模型注册为 Agent */
export async function registerDiscoveredAgent(params: {
  model_name: string
  provider?: string
  endpoint?: string
  workspace_id?: string
}) {
  const { data } = await client.post('/discover/agents/register', null, { params })
  return data
}
