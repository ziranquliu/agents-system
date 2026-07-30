import apiFetch from './client'

export interface AgentMarketItem {
  id: string
  name: string
  description: string
  category: string
  version: string
  author: string
  icon: string
  tags: string[]
  install_count: number
  rating: number
  config_schema: Record<string, any>
}

export interface AgentMarketDetail extends AgentMarketItem {
  system_prompt?: string
  welcome_message?: string
  model_provider?: string
  model_name?: string
  temperature?: number
  max_tokens?: number
  context_window?: number
  enabled_skills?: string[]
  enabled_mcp_servers?: string[]
}

export interface ListMarketParams {
  page?: number
  page_size?: number
  category?: string
  search?: string
}

export interface ListMarketResponse {
  total: number
  page: number
  page_size: number
  items: AgentMarketItem[]
}

export async function listMarketAgents(params: ListMarketParams = {}): Promise<ListMarketResponse> {
  const qs = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '') qs.set(k, String(v)) })
  const resp = await apiFetch(`/api/v1/agents/market${qs.toString() ? `?${qs}` : ''}`, { method: 'GET' })
  return resp.data
}

export async function getMarketAgent(id: string): Promise<AgentMarketDetail> {
  const resp = await apiFetch(`/api/v1/agents/market/${id}`, { method: 'GET' })
  return resp.data
}

export async function installMarketAgent(id: string, config?: Record<string, any>, name?: string): Promise<any> {
  const resp = await apiFetch(`/api/v1/agents/market/${id}/install`, {
    method: 'POST',
    data: { name, config },
  })
  return resp.data
}

export async function listAgentCategories(): Promise<string[]> {
  const resp = await apiFetch('/api/v1/agents/market/categories', { method: 'GET' })
  return resp.data.categories
}
