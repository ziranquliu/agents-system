import apiFetch from './client'

export interface HumanIntervention {
  id: string; conversation_id: string; message_id: string | null
  agent_id: string; intervention_type: string
  original_content: string; modified_content: string | null
  approved: boolean | null; approval_note: string | null
  handled_by: string | null; status: string
  handled_at: string | null; created_at: string | null
}

export interface DialogueRating {
  id: string; conversation_id: string; message_id: string | null
  satisfaction_score: number | null
  relevance_score: number | null; accuracy_score: number | null
  completeness_score: number | null; clarity_score: number | null
  speed_score: number | null; overall_score: number | null
  feedback_text: string | null; feedback_category: string
  rated_by: string | null; rated_by_type: string
  created_at: string | null
}

// HITL
export async function createIntervention(data: Record<string, unknown>): Promise<HumanIntervention> {
  const resp = await apiFetch('/api/v1/dialogue/interventions', { method: 'POST', data })
  return resp.data
}

export async function approveIntervention(id: string, note = ''): Promise<HumanIntervention> {
  const resp = await apiFetch(`/api/v1/dialogue/interventions/${id}/approve`, { method: 'POST', data: { note } })
  return resp.data
}

export async function rejectIntervention(id: string, note = ''): Promise<HumanIntervention> {
  const resp = await apiFetch(`/api/v1/dialogue/interventions/${id}/reject`, { method: 'POST', data: { note } })
  return resp.data
}

export async function modifyInterventionContent(id: string, newContent: string): Promise<HumanIntervention> {
  const resp = await apiFetch(`/api/v1/dialogue/interventions/${id}/modify`, { method: 'POST', data: { new_content: newContent } })
  return resp.data
}

export async function listInterventions(params: Record<string, string | number | undefined> = {}): Promise<{ data: HumanIntervention[]; total: number }> {
  const qs = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => { if (v != null) qs.set(k, String(v)) })
  const resp = await apiFetch(`/api/v1/dialogue/interventions?${qs}`, { method: 'GET' })
  return resp.data
}

// Ratings
export async function createRating(data: Record<string, unknown>): Promise<DialogueRating> {
  const resp = await apiFetch('/api/v1/dialogue/ratings', { method: 'POST', data })
  return resp.data
}

export async function listRatings(params: Record<string, string | number | undefined> = {}): Promise<{ data: DialogueRating[]; total: number }> {
  const qs = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => { if (v != null) qs.set(k, String(v)) })
  const resp = await apiFetch(`/api/v1/dialogue/ratings?${qs}`, { method: 'GET' })
  return resp.data
}

export async function getRatingStats(): Promise<Record<string, unknown>> {
  const resp = await apiFetch('/api/v1/dialogue/ratings/stats', { method: 'GET' })
  return resp.data
}

export async function recordRatingSnapshot(period = 'realtime'): Promise<Record<string, unknown>> {
  const resp = await apiFetch('/api/v1/dialogue/ratings/snapshot', { method: 'POST', data: { period } })
  return resp.data
}

// Export
export function getConversationCsvUrl(conversationId: string): string {
  return `/api/v1/dialogue/export/csv/${conversationId}`
}

export function getConversationPdfUrl(conversationId: string): string {
  return `/api/v1/dialogue/export/pdf-html/${conversationId}`
}

export async function listExportableConversations(params: Record<string, string | number | undefined> = {}): Promise<{ data: any[]; total: number }> {
  const qs = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => { if (v != null) qs.set(k, String(v)) })
  const resp = await apiFetch(`/api/v1/dialogue/export/conversations?${qs}`, { method: 'GET' })
  return resp.data
}
