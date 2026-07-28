import client from './client'
import type { AgentInfo } from './agents'

// ----- Conversation types -----

export interface ConversationInfo {
  id: string
  title: string
  agent_id: string
  user_id: string
  workspace_id: string
  status: string            // active | archived | deleted
  message_count: number
  token_count: number
  compressed: number
  summary: string | null
  created_at: string
  updated_at: string | null
}

export interface ConversationListResponse {
  items: ConversationInfo[]
  total: number
  page: number
  page_size: number
}

// ----- Message types -----

export interface MessageInfo {
  id: string
  conversation_id: string
  role: string               // user | assistant | system | tool
  content: string
  content_type: string       // text | code | image | tool_call
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  model_used: string | null
  tool_calls: string | null
  metadata_json: string | null
  created_at: string
}

export interface MessageListResponse {
  items: MessageInfo[]
  total: number
}

// ----- Enriched types for UI -----

/** 对话 + Agent 名称展开后用于列表展示 */
export interface ConversationListItem extends ConversationInfo {
  agent_name?: string
}

/** 消息 + 关联元数据用于详情展示 */
export interface MessageDisplay extends MessageInfo {
  is_first?: boolean
  agent?: AgentInfo
}

// ----- API functions -----

/** 获取对话列表（分页 + 筛选） */
export async function listConversations(params?: {
  page?: number
  page_size?: number
  status?: string
  search?: string
  agent_id?: string
}) {
  const { data } = await client.get<ConversationListResponse>('/conversations/', { params })
  return data
}

/** 获取单个对话 */
export async function getConversation(id: string) {
  const { data } = await client.get<ConversationInfo>(`/conversations/${id}`)
  return data
}

/** 删除对话 */
export async function deleteConversation(id: string) {
  await client.delete(`/conversations/${id}`)
}

/** 更新对话状态（归档/恢复/删除） */
export async function updateConversationStatus(id: string, status: string) {
  const { data } = await client.patch<ConversationInfo>(`/conversations/${id}/status`, { status })
  return data
}

/** 获取对话的消息列表 */
export async function listMessages(conversationId: string, params?: {
  page?: number
  page_size?: number
}) {
  const { data } = await client.get<MessageListResponse>(
    `/conversations/${conversationId}/messages`,
    { params },
  )
  return data
}
