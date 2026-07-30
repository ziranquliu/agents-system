import apiFetch from './client'

export interface SkillMarketItem {
  id: string
  name: string
  type: string
  version: string
  category: string
  description: string
  icon: string
  author: string
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
  items: SkillMarketItem[]
}

export async function listMarketSkills(params: ListMarketParams = {}): Promise<ListMarketResponse> {
  const qs = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '') qs.set(k, String(v)) })
  const resp = await apiFetch(`/api/v1/skills/market${qs.toString() ? `?${qs}` : ''}`, { method: 'GET' })
  return resp.data
}

export async function getMarketSkill(id: string): Promise<SkillMarketItem> {
  const resp = await apiFetch(`/api/v1/skills/market/${id}`, { method: 'GET' })
  return resp.data
}

export async function installMarketSkill(id: string): Promise<any> {
  const resp = await apiFetch(`/api/v1/skills/market/${id}/install`, { method: 'POST' })
  return resp.data
}

export async function rateMarketSkill(id: string, rating: number): Promise<any> {
  const resp = await apiFetch(`/api/v1/skills/market/${id}/rating`, {
    method: 'POST',
    data: { rating },
  })
  return resp.data
}

export async function listSkillCategories(): Promise<string[]> {
  const resp = await apiFetch('/api/v1/skills/market/categories', { method: 'GET' })
  return resp.data.categories
}
