import client from './client'

// ----- MCP Server (aligned with backend schemas/mcp.py) -----

export interface MCPServerInfo {
  id: string
  name: string
  /** 服务端点 URL（后端 DB 字段为 url，API 响应字段为 endpoint） */
  endpoint: string
  protocol: string           // sse | stdio | streamable-http
  status: string             // online | offline | error
  health_status: string      // healthy | unhealthy | unknown
  version: string | null
  description: string | null
  created_at: string
}

export interface MCPServerListResponse {
  items: MCPServerInfo[]
  total: number
  page: number
  page_size: number
}

export interface MCPServerCreatePayload {
  name: string
  endpoint: string
  protocol?: string
  api_key?: string | null
  description?: string | null
  config?: Record<string, unknown> | null
}

export interface MCPServerUpdatePayload {
  name?: string
  endpoint?: string
  protocol?: string
  api_key?: string | null
  description?: string | null
  config?: Record<string, unknown> | null
}

/** 获取 MCP 服务列表 */
export async function listMCPServers(params?: {
  page?: number
  page_size?: number
  search?: string
  status?: string
  protocol?: string
}) {
  const { data } = await client.get<MCPServerListResponse>('/mcp-servers/', { params })
  return data
}

/** 获取单个 MCP 服务 */
export async function getMCPServer(id: string) {
  const { data } = await client.get<MCPServerInfo>(`/mcp-servers/${id}`)
  return data
}

/** 创建 MCP 服务 */
export async function createMCPServer(payload: MCPServerCreatePayload) {
  const { data } = await client.post<MCPServerInfo>('/mcp-servers/', payload)
  return data
}

/** 更新 MCP 服务 */
export async function updateMCPServer(id: string, payload: MCPServerUpdatePayload) {
  const { data } = await client.put<MCPServerInfo>(`/mcp-servers/${id}`, payload)
  return data
}

/** 删除 MCP 服务 */
export async function deleteMCPServer(id: string) {
  await client.delete(`/mcp-servers/${id}`)
}

/** 健康检查 */
export async function checkMCPHealth(id: string) {
  const { data } = await client.post<MCPServerInfo>(`/mcp-servers/${id}/health-check`)
  return data
}
