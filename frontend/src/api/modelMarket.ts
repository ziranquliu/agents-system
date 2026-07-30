import apiFetch from './client'

export interface ModelMarketItem {
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
  provider: string
  model_name: string
  api_base?: string
  features?: string[]
  pricing?: Record<string, any>
  context_window?: number
  max_tokens?: number
  config_schema?: Record<string, any>
}

export interface ListMarketParams {
  page?: number
  page_size?: number
  category?: string
  search?: string
}

export async function listMarketModels(params: ListMarketParams = {}): Promise<{ total: number; page: number; page_size: number; items: ModelMarketItem[] }> {
  const qs = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '') qs.set(k, String(v)) })
  const resp = await apiFetch(`/api/v1/models/market${qs.toString() ? `?${qs}` : ''}`, { method: 'GET' })
  return resp.data
}

export async function getMarketModel(id: string): Promise<ModelMarketItem> {
  const resp = await apiFetch(`/api/v1/models/market/${id}`, { method: 'GET' })
  return resp.data
}

export async function installMarketModel(id: string, config?: Record<string, any>, name?: string): Promise<any> {
  const resp = await apiFetch(`/api/v1/models/market/${id}/install`, {
    method: 'POST',
    data: { name, config },
  })
  return resp.data
}

export async function listModelCategories(): Promise<string[]> {
  const resp = await apiFetch('/api/v1/models/market/categories', { method: 'GET' })
  return resp.data.categories
}
