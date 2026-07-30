import apiFetch from './client'

export interface Task {
  id: string
  title: string
  description: string | null
  status: string
  priority: string
  assigned_to: string | null
  created_by: string
  due_date: string | null
  created_at: string | null
  updated_at: string | null
}

export async function listTasks(page = 1, pageSize = 50, status?: string, priority?: string, search?: string): Promise<{ items: Task[]; total: number }> {
  const qs = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  if (status) qs.set('status', status)
  if (priority) qs.set('priority', priority)
  if (search) qs.set('search', search)
  const resp = await apiFetch(`/api/v1/tasks?${qs}`, { method: 'GET' })
  return resp.data
}

export async function createTask(title: string, description?: string, priority?: string, assignedTo?: string, dueDate?: string): Promise<Task> {
  const resp = await apiFetch('/api/v1/tasks', { method: 'POST', data: { title, description, priority, assigned_to: assignedTo, due_date: dueDate } })
  return resp.data
}

export async function updateTaskStatus(taskId: string, status: string): Promise<Task> {
  const resp = await apiFetch(`/api/v1/tasks/${taskId}/status`, { method: 'PATCH', data: { status } })
  return resp.data
}

export async function getTaskStats(): Promise<{ total: number; todo: number; in_progress: number; done: number; cancelled: number; by_priority: Record<string, number> }> {
  const resp = await apiFetch('/api/v1/tasks/stats', { method: 'GET' })
  return resp.data
}
