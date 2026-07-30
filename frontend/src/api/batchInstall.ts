import apiFetch from './client'

export interface BatchPrecheckResult {
  status: 'passed' | 'warning' | 'blocked'
  items: Array<{
    skill_id: string
    skill_name: string
    agent_id: string
    dep_check_status: string
    dep_check_detail: Array<Record<string, unknown>>
  }>
  total: number
  passed_count: number
  warning_count: number
  blocked_count: number
  summary: string
}

export interface BatchInstallQueue {
  id: string
  operation: string
  status: string
  total_items: number
  success_count: number
  fail_count: number
  warn_count: number
  precheck_status: string | null
  precheck_summary: string | null
  created_by: string
  created_at: string | null
  completed_at: string | null
}

export interface BatchInstallItem {
  id: string
  queue_id: string
  skill_id: string
  skill_name: string
  agent_id: string
  agent_name: string
  dep_check_status: string
  status: string
  error_message: string | null
  started_at: string | null
  completed_at: string | null
}

// 依赖预检
export async function batchPrecheck(skillIds: string[], agentIds: string[]): Promise<BatchPrecheckResult> {
  const resp = await apiFetch('/api/v1/batch-install/precheck', {
    method: 'POST',
    data: { skill_ids: skillIds, agent_ids: agentIds },
  })
  return resp.data
}

// 创建批量安装
export async function createBatchInstall(skillIds: string[], agentIds: string[], operation = 'install', createdBy = ''): Promise<BatchInstallQueue> {
  const resp = await apiFetch('/api/v1/batch-install', {
    method: 'POST',
    data: { skill_ids: skillIds, agent_ids: agentIds, operation, created_by: createdBy },
  })
  return resp.data
}

// 执行批量安装
export async function executeBatch(queueId: string): Promise<BatchInstallQueue> {
  const resp = await apiFetch(`/api/v1/batch-install/${queueId}/execute`, { method: 'POST' })
  return resp.data
}

// 查询队列列表
export async function listBatchQueues(status?: string, offset = 0, limit = 20): Promise<{ data: BatchInstallQueue[]; total: number }> {
  let url = `/api/v1/batch-install?offset=${offset}&limit=${limit}`
  if (status) url += `&status=${status}`
  const resp = await apiFetch(url, { method: 'GET' })
  return resp.data
}

// 获取队列详情
export async function getBatchQueue(queueId: string): Promise<BatchInstallQueue> {
  const resp = await apiFetch(`/api/v1/batch-install/${queueId}`, { method: 'GET' })
  return resp.data
}

// 获取队列项
export async function getBatchQueueItems(queueId: string, offset = 0, limit = 50): Promise<{ data: BatchInstallItem[]; total: number }> {
  const resp = await apiFetch(`/api/v1/batch-install/${queueId}/items?offset=${offset}&limit=${limit}`, { method: 'GET' })
  return resp.data
}

// 生成报告
export async function getBatchReport(queueId: string): Promise<Record<string, unknown>> {
  const resp = await apiFetch(`/api/v1/batch-install/${queueId}/report`, { method: 'GET' })
  return resp.data
}
