import apiFetch from './client'

export interface SkillReuseRelation {
  id: string
  source_skill_id: string
  source_skill_name: string | null
  source_agent_id: string | null
  target_skill_id: string
  target_skill_name: string | null
  target_agent_id: string
  reuse_mode: string
  sync_mode: string
  status: string
  source_version: string | null
  target_version: string | null
  synced_version: string | null
  last_notified_at: string | null
  last_synced_at: string | null
  reuse_count: number
  created_at: string | null
  updated_at: string | null
}

// 创建复用
export async function createReuse(sourceSkillId: string, targetAgentId: string, reuseMode = 'direct_ref', syncMode = 'manual', sourceAgentId = ''): Promise<SkillReuseRelation> {
  const resp = await apiFetch('/api/v1/skill-reuse', {
    method: 'POST',
    data: { source_skill_id: sourceSkillId, target_agent_id: targetAgentId, reuse_mode: reuseMode, sync_mode: syncMode, source_agent_id: sourceAgentId },
  })
  return resp.data
}

// 删除复用
export async function removeReuse(relationId: string): Promise<void> {
  await apiFetch(`/api/v1/skill-reuse/${relationId}`, { method: 'DELETE' })
}

// 查询列表
export async function listReuses(params: Record<string, string | number | undefined> = {}): Promise<{ data: SkillReuseRelation[]; total: number }> {
  const qs = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null) qs.set(k, String(v)) })
  const resp = await apiFetch(`/api/v1/skill-reuse?${qs}`, { method: 'GET' })
  return resp.data
}

// 检查更新
export async function checkUpdates(sourceSkillId: string): Promise<Array<Record<string, unknown>>> {
  const resp = await apiFetch(`/api/v1/skill-reuse/check-updates/${sourceSkillId}`, { method: 'GET' })
  return resp.data
}

// 同步单条
export async function syncReuse(relationId: string): Promise<Record<string, unknown>> {
  const resp = await apiFetch(`/api/v1/skill-reuse/sync/${relationId}`, { method: 'POST' })
  return resp.data
}

// 同步全部
export async function syncAllReuses(sourceSkillId: string): Promise<{ data: Array<Record<string, unknown>>; total: number }> {
  const resp = await apiFetch(`/api/v1/skill-reuse/sync-all/${sourceSkillId}`, { method: 'POST' })
  return resp.data
}

// 统计
export async function getReuseStats(skillId: string): Promise<Record<string, unknown>> {
  const resp = await apiFetch(`/api/v1/skill-reuse/stats/${skillId}`, { method: 'GET' })
  return resp.data
}

// 排行
export async function getReuseRanking(limit = 10): Promise<Array<Record<string, unknown>>> {
  const resp = await apiFetch(`/api/v1/skill-reuse/ranking?limit=${limit}`, { method: 'GET' })
  return resp.data
}

// 关系图
export async function getReuseGraph(sourceSkillId: string): Promise<{ nodes: Array<Record<string, unknown>>; edges: Array<Record<string, unknown>> }> {
  const resp = await apiFetch(`/api/v1/skill-reuse/graph/${sourceSkillId}`, { method: 'GET' })
  return resp.data
}
