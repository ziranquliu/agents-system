import apiFetch from './client'

export async function checkCircuitBreaker(serverId: string): Promise<any> {
  const resp = await apiFetch(`/api/v1/mcp/optimization/circuit-breaker/${serverId}`, { method: 'GET' })
  return resp.data
}

export async function recordFailure(serverId: string): Promise<any> {
  const resp = await apiFetch(`/api/v1/mcp/optimization/circuit-breaker/${serverId}/failure`, { method: 'POST' })
  return resp.data
}

export async function recordSuccess(serverId: string): Promise<any> {
  const resp = await apiFetch(`/api/v1/mcp/optimization/circuit-breaker/${serverId}/success`, { method: 'POST' })
  return resp.data
}

export async function resetCircuitBreaker(serverId: string): Promise<any> {
  const resp = await apiFetch(`/api/v1/mcp/optimization/circuit-breaker/${serverId}/reset`, { method: 'POST' })
  return resp.data
}

export async function getPoolStats(): Promise<any> {
  const resp = await apiFetch('/api/v1/mcp/optimization/pool', { method: 'GET' })
  return resp.data
}

export async function getLoadBalancer(): Promise<any> {
  const resp = await apiFetch('/api/v1/mcp/optimization/load-balancer', { method: 'GET' })
  return resp.data
}

export async function setLoadBalancerServers(serverIds: string[]): Promise<any> {
  const resp = await apiFetch('/api/v1/mcp/optimization/load-balancer/servers', { method: 'POST', data: { server_ids: serverIds } })
  return resp.data
}

export async function getNextServer(strategy = 'round-robin'): Promise<any> {
  const resp = await apiFetch(`/api/v1/mcp/optimization/load-balancer/next?strategy=${strategy}`, { method: 'GET' })
  return resp.data
}

export async function getSecurityConfig(): Promise<any> {
  const resp = await apiFetch('/api/v1/mcp/optimization/security', { method: 'GET' })
  return resp.data
}

export async function updateSecurityConfig(config: Record<string, any>): Promise<any> {
  const resp = await apiFetch('/api/v1/mcp/optimization/security', { method: 'POST', data: config })
  return resp.data
}
