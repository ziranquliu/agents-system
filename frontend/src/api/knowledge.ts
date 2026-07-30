import apiFetch from './client'

export interface KnowledgeBase {
  id: string
  name: string
  description: string | null
  icon: string
  document_count: number
  chunk_count: number
  status: string
  created_by: string
  created_at: string | null
  updated_at: string | null
}

export interface KnowledgeDocument {
  id: string
  knowledge_base_id: string
  title: string
  content: string | null
  content_type: string
  file_name: string | null
  file_size: number | null
  chunk_count: number
  status: string
  created_by: string | null
  created_at: string | null
}

export interface SearchResult {
  chunk_id: string
  content: string
  chunk_index: number
  token_count: number
  document_id: string
  score: number
}

export async function listKnowledgeBases(page = 1, pageSize = 10, search?: string): Promise<{ items: KnowledgeBase[]; total: number }> {
  const qs = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  if (search) qs.set('search', search)
  const resp = await apiFetch(`/api/v1/knowledge-bases?${qs}`, { method: 'GET' })
  return resp.data
}

export async function createKnowledgeBase(name: string, description?: string, icon?: string): Promise<KnowledgeBase> {
  const resp = await apiFetch('/api/v1/knowledge-bases', { method: 'POST', data: { name, description, icon } })
  return resp.data
}

export async function getKnowledgeBase(id: string): Promise<KnowledgeBase> {
  const resp = await apiFetch(`/api/v1/knowledge-bases/${id}`, { method: 'GET' })
  return resp.data
}

export async function getDocuments(kbId: string, page = 1, pageSize = 20): Promise<{ items: KnowledgeDocument[]; total: number }> {
  const resp = await apiFetch(`/api/v1/knowledge-bases/${kbId}/documents?page=${page}&page_size=${pageSize}`, { method: 'GET' })
  return resp.data
}

export async function addDocument(kbId: string, title: string, content: string, contentType = 'text'): Promise<KnowledgeDocument> {
  const resp = await apiFetch(`/api/v1/knowledge-bases/${kbId}/documents`, { method: 'POST', data: { title, content, content_type: contentType } })
  return resp.data
}

export async function deleteDocument(kbId: string, docId: string): Promise<any> {
  const resp = await apiFetch(`/api/v1/knowledge-bases/${kbId}/documents/${docId}`, { method: 'DELETE' })
  return resp.data
}

export async function searchKnowledge(kbId: string, query: string, topK = 5): Promise<{ results: SearchResult[]; query: string; count: number }> {
  const resp = await apiFetch(`/api/v1/knowledge-bases/${kbId}/search?query=${encodeURIComponent(query)}&top_k=${topK}`, { method: 'GET' })
  return resp.data
}
