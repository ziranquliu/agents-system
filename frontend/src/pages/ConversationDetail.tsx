import { useEffect, useState, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useConversationStore } from '../stores/conversationStore'
import { useAgentStore } from '../stores/agentStore'

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

  const {
    selectedConversation: conv, loading, error,
    messages, messagesLoading,
    fetchConversation, fetchMessages, updateStatus,
  } = useConversationStore()

  const { agents, fetchAgents } = useAgentStore()
  const [statusLoading, setStatusLoading] = useState(false)

  useEffect(() => {
    if (id) {
      fetchConversation(id)
      fetchMessages(id)
    }
    fetchAgents({ pageSize: 100 })
  }, [id])

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

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
              const isTool = msg.role === 'tool'
              const isSystem = msg.role === 'system'

              return (
                <div
                  key={msg.id}
                  className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}
                >
                  {/* Avatar */}
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-sm shrink-0 ${
                      isUser
                        ? 'bg-blue-100'
                        : isSystem
                        ? 'bg-gray-100'
                        : isTool
                        ? 'bg-amber-100'
                        : 'bg-purple-100'
                    }`}
                  >
                    {roleStyle.icon}
                  </div>

                  {/* Message body */}
                  <div className={`max-w-[75%] ${isUser ? 'items-end' : 'items-start'} flex flex-col`}>
                    {/* Role label */}
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

                    {/* Content */}
                    <div
                      className={`rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap break-words ${
                        isUser
                          ? 'bg-blue-600 text-white rounded-tr-md'
                          : isSystem
                          ? 'bg-gray-100 text-gray-600 rounded-tl-md italic'
                          : isTool
                          ? 'bg-amber-50 text-amber-800 rounded-tl-md font-mono text-xs border border-amber-200'
                          : 'bg-gray-100 text-gray-800 rounded-tl-md'
                      }`}
                    >
                      {msg.content}
                    </div>

                    {/* Token info */}
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
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* 底部时间信息 */}
      <div className="bg-white rounded-xl border border-gray-200 px-5 py-2.5 flex items-center justify-between text-xs text-gray-400 shrink-0">
        <span>
          创建于 {new Date(conv.created_at).toLocaleString('zh-CN')}
        </span>
        <span>
          {conv.updated_at
            ? `最后更新 ${new Date(conv.updated_at).toLocaleString('zh-CN')}`
            : ''}
        </span>
      </div>
    </div>
  )
}
