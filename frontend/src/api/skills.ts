import client from './client'

// ----- Skill -----

export interface SkillInfo {
  id: string
  name: string
  version: string
  description: string | null
  type: string | null          // tool | skill | plugin
  category: string | null      // analysis | search | code | etc.
  source: string               // local | marketplace
  source_url: string | null
  icon: string | null
  entry_point: string | null
  parameters: string | null    // JSON
  dependencies: string | null  // JSON
  installed_count: number
  rating: number
  enabled: boolean
  is_system: boolean
  workspace_id: string | null
  created_by: string | null
  created_at: string
  updated_at: string | null
}

export interface SkillListResponse {
  items: SkillInfo[]
  total: number
  page: number
  page_size: number
}

export interface SkillCreatePayload {
  name: string
  version?: string
  description?: string | null
  type?: string | null
  category?: string | null
  entry_point?: string | null
  parameters?: string | null
  dependencies?: string | null
  enabled?: boolean
}

export interface SkillUpdatePayload {
  name?: string
  version?: string
  description?: string | null
  type?: string | null
  category?: string | null
  entry_point?: string | null
  parameters?: string | null
  dependencies?: string | null
  enabled?: boolean
}

/** 获取技能列表 */
export async function listSkills(params?: {
  page?: number
  page_size?: number
  search?: string
  type?: string
  category?: string
}) {
  const { data } = await client.get<SkillListResponse>('/skills/', { params })
  return data
}

/** 获取单个技能 */
export async function getSkill(id: string) {
  const { data } = await client.get<SkillInfo>(`/skills/${id}`)
  return data
}

/** 创建技能 */
export async function createSkill(payload: SkillCreatePayload) {
  const { data } = await client.post<SkillInfo>('/skills/', payload)
  return data
}

/** 更新技能 */
export async function updateSkill(id: string, payload: SkillUpdatePayload) {
  const { data } = await client.put<SkillInfo>(`/skills/${id}`, payload)
  return data
}

/** 删除技能 */
export async function deleteSkill(id: string) {
  await client.delete(`/skills/${id}`)
}

/** 切换启用状态 */
export async function toggleSkill(id: string, enabled: boolean) {
  const { data } = await client.patch<SkillInfo>(`/skills/${id}/toggle`, { enabled })
  return data
}
