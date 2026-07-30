import apiFetch from './client'

export async function getTokenStats(): Promise<any> {
  const resp = await apiFetch('/api/v1/conversations/token-stats', { method: 'GET' })
  return resp.data
}

export async function resetTokenStats(): Promise<any> {
  const resp = await apiFetch('/api/v1/conversations/token-stats/reset', { method: 'POST' })
  return resp.data
}

export async function recordTokenUsage(modelName: string, inputTokens: number, outputTokens: number): Promise<any> {
  const resp = await apiFetch(`/api/v1/conversations/token-usage/record?model_name=${modelName}&input_tokens=${inputTokens}&output_tokens=${outputTokens}`, { method: 'POST' })
  return resp.data
}

export async function optimizeContext(messages: any[], maxTokens = 8000): Promise<any> {
  const resp = await apiFetch(`/api/v1/conversations/context/optimize?max_tokens=${maxTokens}`, { method: 'POST', data: messages })
  return resp.data
}

export async function suggestContextWindow(length: number): Promise<any> {
  const resp = await apiFetch(`/api/v1/conversations/context/suggest?conversation_length=${length}`, { method: 'GET' })
  return resp.data
}

export async function archiveConversation(id: string): Promise<any> {
  const resp = await apiFetch(`/api/v1/conversations/${id}/archive`, { method: 'POST' })
  return resp.data
}

export async function exportConversation(id: string, format = 'json'): Promise<any> {
  const resp = await apiFetch(`/api/v1/conversations/${id}/export?format=${format}`, { method: 'GET' })
  return resp.data
}
