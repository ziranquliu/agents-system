import apiFetch from './client'

export interface MCPMarketItem {
  id: string
  name: string
  description: string
  category: string
  protocol: string
  endpoint_template: string
  version: string
  author: string
  icon: string
  tags: string[]
  install_count: number
  rating: number
  config_schema: Record<string, any>
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
  items: MCPMarketItem[]
}

export async function listMarketMCP(params: ListMarketParams = {}): Promise<ListMarketResponse> {
  const qs = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '') qs.set(k, String(v)) })
  const resp = await apiFetch(`/api/v1/mcp/market${qs.toString() ? `?${qs}` : ''}`, { method: 'GET' })
  return resp.data
}

export async function getMarketMCP(id: string): Promise<MCPMarketItem> {
  const resp = await apiFetch(`/api/v1/mcp/market/${id}`, { method: 'GET' })
  return resp.data
}

export async function installMarketMCP(id: string, config?: Record<string, any>, name?: string): Promise<any> {
  const resp = await apiFetch(`/api/v1/mcp/market/${id}/install`, {
    method: 'POST',
    data: { name, config },
  })
  return resp.data
}

export async function listMCPCategories(): Promise<string[]> {
  const resp = await apiFetch('/api/v1/mcp/market/categories', { method: 'GET' })
  return resp.data.categories
}
