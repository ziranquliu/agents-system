import apiFetch from './client'

export interface User {
  id: string
  username: string
  email: string
  display_name: string | null
  role: string
  is_active: boolean
  avatar_url: string | null
  last_login_at: string | null
  created_at: string | null
  updated_at: string | null
}

export interface UserListResponse {
  total: number
  page: number
  page_size: number
  items: User[]
}

export interface UserUpdateParams {
  display_name?: string
  role?: string
  is_active?: boolean
}

export interface Role {
  id: string
  name: string
  description: string | null
  permissions: string | null
  is_system: boolean
}

export async function listUsers(params: {
  page?: number
  page_size?: number
  role?: string
  is_active?: boolean
  search?: string
} = {}): Promise<UserListResponse> {
  const qs = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') {
      qs.set(k, String(v))
    }
  })
  const query = qs.toString()
  const resp = await apiFetch(`/api/v1/users${query ? `?${query}` : ''}`, { method: 'GET' })
  return resp.data
}

export async function getUser(userId: string): Promise<User> {
  const resp = await apiFetch(`/api/v1/users/${userId}`, { method: 'GET' })
  return resp.data
}

export async function updateUser(userId: string, body: UserUpdateParams): Promise<User> {
  const resp = await apiFetch(`/api/v1/users/${userId}`, {
    method: 'PATCH',
    data: body,
  })
  return resp.data
}

export async function deleteUser(userId: string): Promise<void> {
  await apiFetch(`/api/v1/users/${userId}`, { method: 'DELETE' })
}

export async function listRoles(): Promise<Role[]> {
  const resp = await apiFetch('/api/v1/roles/list', { method: 'GET' })
  return resp.data.roles
}
