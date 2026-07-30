import apiFetch from './client'

export interface AgentMemory {
  id: string
  agent_id: string
  memory_type: string
  title: string
  content: string
  summary: string
  category: string
  tags: string
  keywords: string
  importance_score: number
  access_count: number
  last_accessed_at: string | null
  is_sensitive: boolean
  sensitive_info_type: string
  masked_content: string | null
  source_type: string
  source_id: string | null
  created_by: string | null
  is_public: boolean
  shared_to_agents: string
  is_forgotten: boolean
  forget_reason: string | null
  forgotten_at: string | null
  ttl_seconds: number | null
  expires_at: string | null
  created_at: string | null
  updated_at: string | null
}

export interface MemoryStats {
  total_memories: number
  short_term_count: number
  long_term_count: number
  shared_count: number
  category_distribution: Record<string, number>
  avg_importance: number
  sensitive_count: number
  forgotten_count: number
  ttl_active_count: number
}

// 创建记忆
export async function createMemory(data: Partial<AgentMemory> & { agent_id: string; content: string }): Promise<AgentMemory> {
  const resp = await apiFetch('/api/v1/memories', { method: 'POST', data })
  return resp.data
}

// 获取单条
export async function getMemory(id: string): Promise<AgentMemory> {
  const resp = await apiFetch(`/api/v1/memories/${id}`, { method: 'GET' })
  return resp.data
}

// 更新
export async function updateMemory(id: string, data: Record<string, unknown>): Promise<AgentMemory> {
  const resp = await apiFetch(`/api/v1/memories/${id}`, { method: 'PUT', data })
  return resp.data
}

// 软删除
export async function deleteMemory(id: string, reason = 'manual'): Promise<void> {
  await apiFetch(`/api/v1/memories/${id}?reason=${encodeURIComponent(reason)}`, { method: 'DELETE' })
}

// 硬删除（GDPR）
export async function hardDeleteMemory(id: string): Promise<void> {
  await apiFetch(`/api/v1/memories/${id}/hard`, { method: 'DELETE' })
}

// 查询列表
export interface ListMemoriesParams {
  agent_id?: string
  memory_type?: string
  category?: string
  is_sensitive?: boolean
  is_public?: boolean
  include_forgotten?: boolean
  keyword?: string
  tag?: string
  importance_min?: number
  importance_max?: number
  sort_by?: string
  sort_desc?: boolean
  offset?: number
  limit?: number
}

export async function listMemories(params: ListMemoriesParams = {}): Promise<{ data: AgentMemory[]; total: number; offset: number; limit: number }> {
  const qs = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null) qs.set(k, String(v))
  })
  const resp = await apiFetch(`/api/v1/memories?${qs}`, { method: 'GET' })
  return resp.data
}

// 处理过期记忆
export async function processExpired(): Promise<{ expired_count: number; low_importance_count: number }> {
  const resp = await apiFetch('/api/v1/memories/process-expired', { method: 'POST' })
  return resp.data
}

// 批量遗忘
export async function batchForget(agent_id: string, memory_type?: string): Promise<{ forgotten_count: number }> {
  const resp = await apiFetch('/api/v1/memories/batch-forget', { method: 'POST', data: { agent_id, memory_type } })
  return resp.data
}

// 合并重复
export async function mergeDuplicates(agent_id: string, similarity_threshold = 0.8): Promise<{ merged_count: number }> {
  const resp = await apiFetch('/api/v1/memories/merge-duplicates', { method: 'POST', data: { agent_id, similarity_threshold } })
  return resp.data
}

// 获取统计
export async function getMemoryStats(agent_id: string): Promise<MemoryStats> {
  const resp = await apiFetch(`/api/v1/memories/stats/${agent_id}`, { method: 'GET' })
  return resp.data
}

// 记录快照
export async function recordSnapshot(agent_id: string): Promise<{ id: string; agent_id: string; total_memories: number; created_at: string | null }> {
  const resp = await apiFetch(`/api/v1/memories/snapshot/${agent_id}`, { method: 'POST' })
  return resp.data
}

// GDPR 删除
export async function gdprDeleteUser(user_id: string): Promise<void> {
  await apiFetch(`/api/v1/memories/gdpr/user/${user_id}`, { method: 'DELETE' })
}

// GDPR 导出
export async function gdprExportUser(user_id: string): Promise<AgentMemory[]> {
  const resp = await apiFetch(`/api/v1/memories/gdpr/export/${user_id}`, { method: 'GET' })
  return resp.data
}
