import apiFetch from './client'

export interface CollaborationTask {
  id: string
  collaboration_id: string
  agent_id: string
  agent_name: string | null
  order: number
  role: string | null
  input_text: string | null
  output_text: string | null
  status: string
  error_message: string | null
  started_at: string | null
  completed_at: string | null
}

export interface Collaboration {
  id: string
  name: string
  description: string | null
  mode: string
  status: string
  context: Record<string, any> | null
  result: Record<string, any> | null
  created_by: string
  created_at: string | null
  updated_at: string | null
}

export interface CollaborationMode {
  id: string
  name: string
  description: string
  icon: string
}

export interface TaskCreate {
  agent_id: string
  agent_name?: string
  order?: number
  role?: string
  input_text?: string
}

export interface CollaborationCreate {
  name: string
  description?: string
  mode: string
  context?: Record<string, any>
  tasks: TaskCreate[]
}

export async function listCollaborations(page = 1, pageSize = 10, mode?: string, status?: string): Promise<{ items: Collaboration[]; total: number }> {
  const qs = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  if (mode) qs.set('mode', mode)
  if (status) qs.set('status', status)
  const resp = await apiFetch(`/api/v1/collaborations?${qs}`, { method: 'GET' })
  return resp.data
}

export async function getCollaboration(id: string): Promise<Collaboration> {
  const resp = await apiFetch(`/api/v1/collaborations/${id}`, { method: 'GET' })
  return resp.data
}

export async function createCollaboration(data: CollaborationCreate): Promise<{ id: string; name: string; mode: string; status: string }> {
  const resp = await apiFetch('/api/v1/collaborations', { method: 'POST', data })
  return resp.data
}

export async function startCollaboration(id: string): Promise<{ message: string; collaboration: Collaboration }> {
  const resp = await apiFetch(`/api/v1/collaborations/${id}/start`, { method: 'POST' })
  return resp.data
}

export async function getCollaborationTasks(id: string): Promise<{ tasks: CollaborationTask[] }> {
  const resp = await apiFetch(`/api/v1/collaborations/${id}/tasks`, { method: 'GET' })
  return resp.data
}

export async function addTask(collabId: string, data: TaskCreate): Promise<CollaborationTask> {
  const resp = await apiFetch(`/api/v1/collaborations/${collabId}/tasks`, { method: 'POST', data })
  return resp.data
}

export async function listCollaborationModes(): Promise<{ modes: CollaborationMode[] }> {
  const resp = await apiFetch('/api/v1/collaborations/modes', { method: 'GET' })
  return resp.data
}
