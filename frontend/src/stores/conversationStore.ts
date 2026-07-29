import { create } from 'zustand'
import type { ConversationInfo, ConversationListItem } from '../api/conversations'
import * as convApi from '../api/conversations'
import { chatStream } from '../api/chat'

interface ConversationState {
  // 列表
  conversations: ConversationListItem[]
  total: number
  page: number
  pageSize: number
  search: string
  statusFilter: string
  agentFilter: string
  loading: boolean
  error: string | null

  // 详情
  selectedConversation: ConversationInfo | null
  messages: convApi.MessageInfo[]
  messagesTotal: number
  messagesLoading: boolean

  // 流式发送
  sending: boolean
  streamingText: string
  abortStream: (() => void) | null
  transportMode: 'sse' | 'websocket'

  fetchConversations: (opts?: {
    page?: number
    pageSize?: number
    search?: string
    status?: string
    agent_id?: string
  }) => Promise<void>
  fetchConversation: (id: string) => Promise<void>
  deleteConversation: (id: string) => Promise<void>
  updateStatus: (id: string, status: string) => Promise<void>
  fetchMessages: (conversationId: string, opts?: {
    page?: number
    pageSize?: number
  }) => Promise<void>

  sendMessage: (conversationId: string, content: string, model?: string) => Promise<void>
  stopStream: () => void
  startStream: () => void
  appendStream: (text: string) => void
  finishStream: (conversationId: string, fullText: string) => Promise<void>
  resetStream: () => void
  setTransportMode: (mode: 'sse' | 'websocket') => void

  setSearch: (search: string) => void
  setStatusFilter: (status: string) => void
  setAgentFilter: (agent_id: string) => void
  setPage: (page: number) => void
}

export const useConversationStore = create<ConversationState>((set, get) => ({
  conversations: [],
  total: 0,
  page: 1,
  pageSize: 20,
  search: '',
  statusFilter: '',
  agentFilter: '',
  loading: false,
  error: null,

  selectedConversation: null,
  messages: [],
  messagesTotal: 0,
  messagesLoading: false,

  // 流式发送初始状态
  sending: false,
  streamingText: '',
  abortStream: null,
  transportMode: 'sse',

  fetchConversations: async (opts) => {
    const { page, pageSize, search, statusFilter, agentFilter } = {
      ...get(),
      ...opts,
    }
    set({ loading: true, error: null })
    try {
      const params: Record<string, string | number> = {
        page: opts?.page ?? page,
        page_size: opts?.pageSize ?? pageSize,
      }
      const qSearch = opts?.search ?? search
      const qStatus = opts?.status ?? statusFilter
      const qAgent = opts?.agent_id ?? agentFilter
      if (qSearch) params.search = qSearch
      if (qStatus) params.status = qStatus
      if (qAgent) params.agent_id = qAgent

      const res = await convApi.listConversations(params)
      set({
        conversations: res.items as ConversationListItem[],
        total: res.total,
        page: params.page as number,
        pageSize: params.page_size as number,
        loading: false,
      })
    } catch (e: any) {
      set({
        loading: false,
        error:
          e?.response?.data?.detail ||
          e?.message ||
          '获取对话列表失败',
      })
    }
  },

  fetchConversation: async (id: string) => {
    set({ loading: true, error: null })
    try {
      const conv = await convApi.getConversation(id)
      set({ selectedConversation: conv, loading: false })
    } catch (e: any) {
      set({
        loading: false,
        error:
          e?.response?.data?.detail ||
          e?.message ||
          '获取对话详情失败',
      })
    }
  },

  deleteConversation: async (id: string) => {
    set({ error: null })
    try {
      await convApi.deleteConversation(id)
      get().fetchConversations()
    } catch (e: any) {
      set({
        error:
          e?.response?.data?.detail ||
          e?.message ||
          '删除对话失败',
      })
    }
  },

  updateStatus: async (id: string, status: string) => {
    try {
      const conv = await convApi.updateConversationStatus(id, status)
      set({ selectedConversation: conv })
      // 同步更新列表中的状态
      const updated = get().conversations.map((c) =>
        c.id === id ? { ...c, status: conv.status } : c,
      )
      set({ conversations: updated })
    } catch (e: any) {
      throw e
    }
  },

  fetchMessages: async (conversationId, opts) => {
    set({ messagesLoading: true })
    try {
      const res = await convApi.listMessages(conversationId, opts)
      set({
        messages: res.items,
        messagesTotal: res.total,
        messagesLoading: false,
      })
    } catch (e: any) {
      set({ messagesLoading: false })
    }
  },

  sendMessage: async (conversationId, content, model = 'gpt-4o-mini') => {
    const prevMessages = get().messages
    const userMessage: convApi.MessageInfo = {
      id: `temp_${Date.now()}`,
      conversation_id: conversationId,
      role: 'user',
      content,
      content_type: 'text',
      prompt_tokens: 0,
      completion_tokens: 0,
      total_tokens: 0,
      model_used: null,
      tool_calls: null,
      metadata_json: null,
      created_at: new Date().toISOString(),
    }
    // 立即显示用户消息
    set({ messages: [...prevMessages, userMessage], sending: true, streamingText: '' })

    const abort = chatStream(
      {
        model,
        messages: [{ role: 'user', content }],
      },
      {
        onChunk: (text) => {
          set({ streamingText: get().streamingText + text })
        },
        onDone: async (fullText) => {
          const assistantMsg: convApi.MessageInfo = {
            id: `msg_${Date.now()}`,
            conversation_id: conversationId,
            role: 'assistant',
            content: fullText,
            content_type: 'text',
            prompt_tokens: 0,
            completion_tokens: 0,
            total_tokens: 0,
            model_used: model,
            tool_calls: null,
            metadata_json: null,
            created_at: new Date().toISOString(),
          }
          set({
            messages: [...get().messages, assistantMsg],
            sending: false,
            streamingText: '',
            abortStream: null,
          })
          // 刷新消息列表
          await get().fetchMessages(conversationId)
        },
        onError: (err) => {
          set({ sending: false, streamingText: '', abortStream: null })
          console.error('Chat stream error:', err)
        },
      },
    )
    set({ abortStream: abort })
  },

  stopStream: () => {
    const abort = get().abortStream
    if (abort) {
      abort()
      set({ sending: false, streamingText: '', abortStream: null })
    }
  },

  // 以下方法由 WebSocket 模式调用，统一流式状态管理
  startStream: () => {
    set({ sending: true, streamingText: '' })
  },

  appendStream: (text) => {
    set({ streamingText: get().streamingText + text })
  },

  finishStream: async (conversationId, fullText) => {
    const assistantMsg: convApi.MessageInfo = {
      id: `msg_${Date.now()}`,
      conversation_id: conversationId,
      role: 'assistant',
      content: fullText,
      content_type: 'text',
      prompt_tokens: 0,
      completion_tokens: 0,
      total_tokens: 0,
      model_used: null,
      tool_calls: null,
      metadata_json: null,
      created_at: new Date().toISOString(),
    }
    set({
      messages: [...get().messages, assistantMsg],
      sending: false,
      streamingText: '',
      abortStream: null,
    })
    await get().fetchMessages(conversationId)
  },

  resetStream: () => {
    set({ sending: false, streamingText: '', abortStream: null })
  },

  setTransportMode: (mode) => {
    set({ transportMode: mode })
  },

  setSearch: (search) => {
    set({ search, page: 1 })
    get().fetchConversations({ search, page: 1 })
  },
  setStatusFilter: (status) => {
    set({ statusFilter: status, page: 1 })
    get().fetchConversations({ status, page: 1 })
  },
  setAgentFilter: (agent_id) => {
    set({ agentFilter: agent_id, page: 1 })
    get().fetchConversations({ agent_id, page: 1 })
  },
  setPage: (page) => {
    set({ page })
    get().fetchConversations({ page })
  },
}))
