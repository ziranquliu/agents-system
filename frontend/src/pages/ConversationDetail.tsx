import { useEffect, useState, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useConversationStore } from '../stores/conversationStore'
import { useAgentStore } from '../stores/agentStore'
import { useModelConfigStore } from '../stores/modelConfigStore'
import { useAuthStore } from '../stores/authStore'
import { useWebSocket } from '../hooks/useWebSocket'
import * as convApi from '../api/conversations'

const statusConfig: Record<string, { label: string; color: string }> = {
  active: { label: '活跃', color: 'bg-green-100 text-green-700' },
  archived: { label: '已归档', color: 'bg-slate-100 text-slate-600' },
  deleted: { label: '已删除', color: 'bg-red-100 text-red-600' },
}

const roleConfig: Record<string, { label: string; color: string; icon: string }> = {
  user: { label: '用户', color: 'bg-blue-100 text-blue-700', icon: '👤' },
  assistant: { label: 'AI 助手', color: 'bg-purple-100 text-purple-700', icon: '🤖' },
  system: { label: '系统', color: 'bg-gray-100 text-gray-600', icon: '⚙️' },
  tool: { label: '工具调用', color: 'bg-amber-100 text-amber-700', icon: '🔧' },
}

export default function ConversationDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const {
    selectedConversation: conv, loading, error,
    messages, messagesLoading,
    sending, streamingText,
    transportMode,
    fetchConversation, fetchMessages, updateStatus,
    sendMessage, stopStream,
    startStream, appendStream, finishStream, resetStream, setTransportMode,
  } = useConversationStore()

  const { agents, fetchAgents } = useAgentStore()
  const { items: models, fetch: fetchModels } = useModelConfigStore()
  const { token } = useAuthStore()

  const [statusLoading, setStatusLoading] = useState(false)
  const [inputText, setInputText] = useState('')
  const [selectedModel, setSelectedModel] = useState('gpt-4o-mini')

  // WebSocket hook —— autoConnect=false，由切换按钮手动管理连接
  const ws = useWebSocket({
    conversationId: id || '',
    token: token || '',
    autoConnect: false,
    onChunk: (text) => {
      if (useConversationStore.getState().transportMode === 'websocket') {
        appendStream(text)
      }
    },
    onDone: (fullText) => {
      const state = useConversationStore.getState()
      if (state.transportMode === 'websocket' && id) {
        finishStream(id, fullText)
      }
    },
    onError: () => {
      if (useConversationStore.getState().transportMode === 'websocket') {
        resetStream()
      }
    },
  })

  // WebSocket 生命周期：切换模式时连接/断开
  useEffect(() => {
    if (transportMode === 'websocket' && id) {
      if (ws.status === 'disconnected' || ws.status === 'error') {
        ws.connect()
      }
    } else {
      ws.disconnect()
    }
  }, [transportMode, id])

  // 如果 id 变了，重新拉取
  useEffect(() => {
    if (id) {
      fetchConversation(id)
      fetchMessages(id)
    }
    fetchAgents({ pageSize: 100 })
    fetchModels()
  }, [id])

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingText])

  const handleSend = async () => {
    const text = inputText.trim()
    if (!text || !id || sending) return
    setInputText('')

    if (transportMode === 'websocket') {
      // ====== WebSocket 发送 ======
      const userMessage: convApi.MessageInfo = {
        id: `temp_${Date.now()}`,
        conversation_id: id,
        role: 'user',
        content: text,
        content_type: 'text',
        prompt_tokens: 0,
        completion_tokens: 0,
        total_tokens: 0,
        model_used: null,
        tool_calls: null,
        metadata_json: null,
        created_at: new Date().toISOString(),
      }
      useConversationStore.setState({
        messages: [...useConversationStore.getState().messages, userMessage],
      })
      startStream()

      // 确保已连接
      if (ws.status !== 'connected') {
        ws.connect()
        await new Promise((r) => setTimeout(r, 600))
      }
      ws.send(text, selectedModel)
    } else {
      // ====== SSE 发送（原有行为） ======
      await sendMessage(id, text, selectedModel)
    }
  }

  const handleStop = () => {
    if (transportMode === 'websocket') {
      ws.disconnect()
      resetStream()
    } else {
      stopStream()
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleArchive = async () => {
    if (!id || !conv) return
    setStatusLoading(true)
    const target = conv.status === 'archived' ? 'active' : 'archived'
    try {
      await updateStatus(id, target)
    } catch {
      alert('操作失败')
    } finally {
      setStatusLoading(false)
    }
  }

  const handleDelete = async () => {
    if (!id || !conv) return
    if (!window.confirm(`确定要删除此对话吗？`)) return
    try {
      await useConversationStore.getState().deleteConversation(id)
      navigate('/conversations')
    } catch {
      alert('删除失败')
    }
  }

  // Loading state
  if (loading && !conv) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-400">加载中...</div>
      </div>
    )
  }

  // Error state
  if (error && !conv) {
    return (
      <div className="space-y-4">
        <div className="bg-red-50 text-red-600 text-sm px-4 py-3 rounded-lg border border-red-100">
          {error}
        </div>
        <button
          onClick={() => navigate('/conversations')}
          className="text-blue-600 hover:text-blue-700 text-sm"
        >
          ← 返回列表
        </button>
      </div>
    )
  }

  if (!conv) return null

  const agentName =
    agents.find((a) => a.id === conv.agent_id)?.name ||
    conv.agent_id.slice(0, 8) + '...'

  const currentStatus = statusConfig[conv.status] || {
    label: conv.status,
    color: 'bg-gray-100 text-gray-600',
  }

  const wsStatusHint: Record<string, string> = {
    connected: 'WebSocket 已连接',
    connecting: '连接中...',
    disconnected: '未连接',
    error: '连接异常',
  }

  return (
    <div className="flex flex-col h-[calc(100vh-7rem)] space-y-4">
      {/* 顶部导航和信息 */}
      <div className="bg-white rounded-xl border border-gray-200 px-5 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/conversations')}
            className="text-gray-500 hover:text-gray-700 transition-colors text-sm"
          >
            ← 返回
          </button>
          <span className="text-gray-300">/</span>
          <div>
            <h1 className="text-base font-semibold text-gray-900">
              {conv.title || '未命名对话'}
            </h1>
            <div className="flex items-center gap-3 mt-0.5">
              <span className="text-xs text-gray-500">Agent: {agentName}</span>
              <span
                className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${currentStatus.color}`}
              >
                {currentStatus.label}
              </span>
              <span className="text-xs text-gray-400">
                {conv.message_count} 条消息 ·{' '}
                {conv.token_count > 1000
                  ? `${(conv.token_count / 1000).toFixed(1)}K`
                  : conv.token_count}{' '}
                Token
              </span>
              {conv.summary && (
                <span className="text-xs text-gray-400 truncate max-w-[300px]">
                  · {conv.summary}
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleArchive}
            disabled={statusLoading}
            className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50"
          >
            {conv.status === 'archived' ? '恢复' : '归档'}
          </button>
          <button
            onClick={handleDelete}
            className="px-3 py-1.5 text-sm text-red-600 border border-red-200 rounded-lg hover:bg-red-50 transition-colors"
          >
            删除
          </button>
        </div>
      </div>

      {/* 消息列表区域 */}
      <div className="flex-1 bg-white rounded-xl border border-gray-200 overflow-hidden flex flex-col min-h-0">
        {messagesLoading && messages.length === 0 ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-gray-400">加载消息中...</div>
          </div>
        ) : messages.length === 0 ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <div className="text-4xl mb-3">💬</div>
              <p className="text-gray-400">暂无消息</p>
              <p className="text-gray-300 text-sm mt-1">
                此对话尚未包含任何消息
              </p>
            </div>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-4">
            {messages.map((msg) => {
              const roleStyle = roleConfig[msg.role] || {
                label: msg.role,
                color: 'bg-gray-100 text-gray-600',
                icon: '💬',
              }
              const isUser = msg.role === 'user'

              return (
                <div
                  key={msg.id}
                  className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}
                >
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-sm shrink-0 ${
                      isUser
                        ? 'bg-blue-100'
                        : msg.role === 'system'
                        ? 'bg-gray-100'
                        : msg.role === 'tool'
                        ? 'bg-amber-100'
                        : 'bg-purple-100'
                    }`}
                  >
                    {roleStyle.icon}
                  </div>
                  <div className={`max-w-[75%] ${isUser ? 'items-end' : 'items-start'} flex flex-col`}>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-medium text-gray-500">
                        {isUser ? '用户' : roleStyle.label}
                      </span>
                      {msg.model_used && (
                        <span className="text-xs text-gray-400">{msg.model_used}</span>
                      )}
                      <span className="text-xs text-gray-300">
                        {new Date(msg.created_at).toLocaleTimeString('zh-CN')}
                      </span>
                    </div>
                    <div
                      className={`rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap break-words ${
                        isUser
                          ? 'bg-blue-600 text-white rounded-tr-md'
                          : msg.role === 'system'
                          ? 'bg-gray-100 text-gray-600 rounded-tl-md italic'
                          : msg.role === 'tool'
                          ? 'bg-amber-50 text-amber-800 rounded-tl-md font-mono text-xs border border-amber-200'
                          : 'bg-gray-100 text-gray-800 rounded-tl-md'
                      }`}
                    >
                      {msg.content}
                    </div>
                    {msg.total_tokens > 0 && (
                      <div className="flex items-center gap-3 mt-1 px-1">
                        <span className="text-xs text-gray-400">
                          tokens: {msg.prompt_tokens}↑ {msg.completion_tokens}↓
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              )
            })}

            {/* 流式消息 */}
            {sending && streamingText && (
              <div className="flex gap-3">
                <div className="w-8 h-8 rounded-full flex items-center justify-center text-sm shrink-0 bg-purple-100">
                  🤖
                </div>
                <div className="max-w-[75%] flex flex-col items-start">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-medium text-gray-500">AI 助手</span>
                    {transportMode === 'websocket' && (
                      <span className="text-xs text-green-500">● WS</span>
                    )}
                  </div>
                  <div className="rounded-2xl rounded-tl-md px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap break-words bg-gray-100 text-gray-800">
                    {streamingText}
                    <span className="inline-block w-2 h-4 bg-purple-600 animate-pulse ml-0.5"></span>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* 消息输入区域 */}
      <div className="bg-white rounded-xl border border-gray-200 px-4 py-3 shrink-0">
        <div className="flex items-center gap-2">
          {/* 模型选择 */}
          <select
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            disabled={sending}
            className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 bg-white text-gray-600 focus:outline-none focus:border-blue-400 shrink-0"
          >
            <optgroup label="模型配置">
              {models.length > 0
                ? models.map((m) => (
                    <option key={m.id} value={m.model_name}>
                      {m.name}
                    </option>
                  ))
                : null}
            </optgroup>
            <option value="gpt-4o-mini">GPT-4o-mini</option>
            <option value="deepseek-chat">DeepSeek-V3</option>
          </select>

          {/* 传输模式切换 */}
          <button
            onClick={() => setTransportMode(transportMode === 'sse' ? 'websocket' : 'sse')}
            disabled={sending}
            className={`shrink-0 flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-lg border transition-colors ${
              transportMode === 'websocket'
                ? 'bg-green-50 border-green-200 text-green-700'
                : 'bg-blue-50 border-blue-200 text-blue-700'
            }`}
            title={wsStatusHint[ws.status]}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                transportMode === 'websocket'
                  ? ws.status === 'connected'
                    ? 'bg-green-500'
                    : ws.status === 'connecting'
                    ? 'bg-yellow-500 animate-pulse'
                    : 'bg-red-400'
                  : 'bg-blue-500'
              }`}
            />
            {transportMode === 'websocket' ? 'WebSocket' : 'SSE'}
          </button>

          {/* 输入框 */}
          <textarea
            ref={inputRef}
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={sending ? 'AI 正在回复...' : '输入消息，Enter 发送，Shift+Enter 换行'}
            disabled={sending}
            rows={1}
            className="flex-1 resize-none text-sm border-0 focus:ring-0 outline-none px-2 py-1.5 text-gray-800 placeholder:text-gray-400 disabled:bg-transparent"
          />

          {/* 发送 / 停止按钮 */}
          {sending ? (
            <button
              onClick={handleStop}
              className="shrink-0 px-3 py-1.5 text-sm bg-red-500 hover:bg-red-600 text-white rounded-lg transition-colors flex items-center gap-1"
            >
              <span>■</span> 停止
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={!inputText.trim() || (transportMode === 'websocket' && ws.status === 'connecting')}
              className="shrink-0 px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-700 disabled:bg-gray-200 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
            >
              {transportMode === 'websocket' && ws.status === 'connecting' ? '连接中...' : '发送'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
