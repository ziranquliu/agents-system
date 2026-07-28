import client from './client'

// ----- Workspace -----

export interface WorkspaceInfo {
  id: string
  name: string
  description: string | null
  owner_id: string
  member_count: number
  is_active: boolean
  created_at: string
  updated_at: string | null
}

export interface WorkspaceListResponse {
  items: WorkspaceInfo[]
  total: number
  page: number
  page_size: number
}

export interface WorkspaceCreatePayload {
  name: string
  description?: string | null
}

export interface WorkspaceUpdatePayload {
  name?: string
  description?: string | null
  is_active?: boolean
}

/** 获取工作空间列表 */
export async function listWorkspaces(params?: {
  page?: number
  page_size?: number
  search?: string
}) {
  const { data } = await client.get<WorkspaceListResponse>('/workspaces/', { params })
  return data
}

/** 获取单个工作空间 */
export async function getWorkspace(id: string) {
  const { data } = await client.get<WorkspaceInfo>(`/workspaces/${id}`)
  return data
}

/** 创建工作空间 */
export async function createWorkspace(payload: WorkspaceCreatePayload) {
  const { data } = await client.post<WorkspaceInfo>('/workspaces/', payload)
  return data
}

/** 更新工作空间 */
export async function updateWorkspace(id: string, payload: WorkspaceUpdatePayload) {
  const { data } = await client.put<WorkspaceInfo>(`/workspaces/${id}`, payload)
  return data
}

/** 删除工作空间 */
export async function deleteWorkspace(id: string) {
  await client.delete(`/workspaces/${id}`)
}
