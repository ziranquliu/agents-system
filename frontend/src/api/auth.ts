import client from './client'

export interface UserInfo {
  id: string
  username: string
  email: string
  display_name: string | null
  role: string
  is_active: boolean
  avatar_url: string | null
  last_login_at: string | null
  created_at: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: UserInfo
}

/** 登录 */
export async function login(username: string, password: string) {
  const { data } = await client.post<LoginResponse>('/auth/login', {
    username,
    password,
  })
  return data
}

/** 获取当前用户信息 */
export async function getMe() {
  const { data } = await client.get<UserInfo>('/auth/me')
  return data
}

/** 登出 */
export async function logout() {
  await client.post('/auth/logout')
}
