import apiFetch from './client'

export async function getCacheStats(): Promise<{ cache_type: string; capacity: number; size: number; hits: number; misses: number; hit_rate: number }> {
  const resp = await apiFetch('/api/v1/skills/optimization/cache-stats', { method: 'GET' })
  return resp.data
}

export async function clearCache(): Promise<{ message: string; stats: any }> {
  const resp = await apiFetch('/api/v1/skills/optimization/cache-clear', { method: 'POST' })
  return resp.data
}

export async function getExecutionStats(skillId?: string): Promise<any> {
  const qs = skillId ? `?skill_id=${skillId}` : ''
  const resp = await apiFetch(`/api/v1/skills/optimization/execution-stats${qs}`, { method: 'GET' })
  return resp.data
}

export async function getDagPlan(skillIds: string[]): Promise<{ skill_ids: string[]; levels: string[][]; level_count: number; suggestion: string }> {
  const resp = await apiFetch(`/api/v1/skills/optimization/dag-plan?skill_ids=${skillIds.join(',')}`, { method: 'GET' })
  return resp.data
}

export async function recordExecution(skillId: string, durationMs: number): Promise<any> {
  const resp = await apiFetch(`/api/v1/skills/optimization/record-execution?skill_id=${skillId}&duration_ms=${durationMs}`, { method: 'POST' })
  return resp.data
}
