import client from './client'

// ----- MCP Server -----

export interface MCPServerInfo {
  id: string
  name: string
  url: string
  protocol: string           // sse | stdio | websocket
  status: string             // active | inactive | error
  version: string | null
  description: string | null
  auth_type: string | null   // none | api_key | bearer | basic
  auth_config: string | null // JSON
  health_check_url: string | null
  last_health_check: string | null
  health_status: string      // healthy | unhealthy | unknown
  config: string | null      // JSON
  workspace_id: string | null
  created_by: string | null
  created_at: string
  updated_at: string | null
}

export interface MCPServerListResponse {
  items: MCPServerInfo[]
  total: number
  page: number
  page_size: number
}

export interface MCPServerCreatePayload {
  name: string
  url: string
  protocol?: string
  version?: string | null
  description?: string | null
  auth_type?: string | null
  auth_config?: string | null
  health_check_url?: string | null
}

export interface MCPServerUpdatePayload {
  name?: string
  url?: string
  protocol?: string
  version?: string | null
  description?: string | null
  auth_type?: string | null
  auth_config?: string | null
  health_check_url?: string | null
}

/** 获取 MCP 服务列表 */
export async function listMCPServers(params?: {
  page?: number
  page_size?: number
  search?: string
  status?: string
}) {
  const { data } = await client.get<MCPServerListResponse>('/mcp/', { params })
  return data
}

/** 获取单个 MCP 服务 */
export async function getMCPServer(id: string) {
  const { data } = await client.get<MCPServerInfo>(`/mcp/${id}`)
  return data
}

/** 创建 MCP 服务 */
export async function createMCPServer(payload: MCPServerCreatePayload) {
  const { data } = await client.post<MCPServerInfo>('/mcp/', payload)
  return data
}

/** 更新 MCP 服务 */
export async function updateMCPServer(id: string, payload: MCPServerUpdatePayload) {
  const { data } = await client.put<MCPServerInfo>(`/mcp/${id}`, payload)
  return data
}

/** 删除 MCP 服务 */
export async function deleteMCPServer(id: string) {
  await client.delete(`/mcp/${id}`)
}

/** 健康检查 */
export async function checkMCPHealth(id: string) {
  const { data } = await client.post<MCPServerInfo>(`/mcp/${id}/health-check`)
  return data
}
