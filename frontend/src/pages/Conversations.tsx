import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useConversationStore } from '../stores/conversationStore'
import { useAgentStore } from '../stores/agentStore'

const statusConfig: Record<string, { label: string; color: string }> = {
  active: { label: '活跃', color: 'bg-green-100 text-green-700' },
  archived: { label: '已归档', color: 'bg-slate-100 text-slate-600' },
  deleted: { label: '已删除', color: 'bg-red-100 text-red-600' },
}

export default function Conversations() {
  const {
    conversations, total, page, pageSize, loading, error,
    fetchConversations, deleteConversation, updateStatus,
    setSearch, setStatusFilter, setPage,
  } = useConversationStore()

  const { agents, fetchAgents } = useAgentStore()
  const [searchInput, setSearchInput] = useState('')
  const [statusTab, setStatusTab] = useState('')

  useEffect(() => {
    fetchConversations()
    fetchAgents({ pageSize: 100 })
  }, [])

  const totalPages = Math.ceil(total / pageSize)

  const handleSearch = () => {
    setSearch(searchInput)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSearch()
  }

  const handleDelete = async (id: string, title: string) => {
    if (!window.confirm(`确定要删除对话「${title || '未命名对话'}」吗？`)) return
    await deleteConversation(id)
  }

  const handleArchive = async (id: string, currentStatus: string) => {
    const targetStatus = currentStatus === 'archived' ? 'active' : 'archived'
    try {
      await updateStatus(id, targetStatus)
    } catch {
      alert('操作失败')
    }
  }

  // Map agent names
  const agentMap = new Map(agents.map((a) => [a.id, a.name]))

  const tabs = [
    { value: '', label: '全部' },
    { value: 'active', label: '活跃' },
    { value: 'archived', label: '已归档' },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">对话管理</h1>
        <p className="text-gray-500 mt-1">查看和管理所有对话历史</p>
      </div>

      {/* 状态 Tab */}
      <div className="flex gap-1 bg-gray-100 p-1 rounded-lg w-fit">
        {tabs.map((tab) => (
          <button
            key={tab.value}
            onClick={() => {
              setStatusTab(tab.value)
              setStatusFilter(tab.value)
            }}
            className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors ${
              (statusTab || '') === tab.value
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* 筛选栏 */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <div className="flex flex-wrap gap-4 items-center">
          <div className="flex-1 min-w-[200px]">
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={handleKeyDown}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none text-sm"
              placeholder="搜索对话标题..."
            />
          </div>
          <button
            onClick={handleSearch}
            className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm transition-colors"
          >
            搜索
          </button>
        </div>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="bg-red-50 text-red-600 text-sm px-4 py-3 rounded-lg border border-red-100">
          {error}
        </div>
      )}

      {/* 对话列表 */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {loading && conversations.length === 0 ? (
          <div className="p-12 text-center text-gray-400">加载中...</div>
        ) : conversations.length === 0 ? (
          <div className="p-12 text-center">
            <div className="text-4xl mb-3">💬</div>
            <p className="text-gray-400">暂无对话记录</p>
            <p className="text-gray-300 text-sm mt-1">
              当用户与 Agent 开始对话后，记录将出现在这里
            </p>
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50/50">
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">标题</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">Agent</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">状态</th>
                <th className="text-center px-4 py-3 text-sm font-medium text-gray-500">消息数</th>
                <th className="text-center px-4 py-3 text-sm font-medium text-gray-500">Token</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">更新时间</th>
                <th className="text-right px-4 py-3 text-sm font-medium text-gray-500">操作</th>
              </tr>
            </thead>
            <tbody>
              {conversations.map((conv) => (
                <tr
                  key={conv.id}
                  className="border-b border-gray-50 hover:bg-gray-50 transition-colors"
                >
                  <td className="px-4 py-3">
                    <Link
                      to={`/conversations/${conv.id}`}
                      className="text-sm font-medium text-blue-600 hover:text-blue-700"
                    >
                      {conv.title || '未命名对话'}
                    </Link>
                    {conv.summary && (
                      <p className="text-xs text-gray-400 mt-0.5 truncate max-w-[240px]">
                        {conv.summary}
                      </p>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {agentMap.get(conv.agent_id) || conv.agent_id.slice(0, 8) + '...'}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        statusConfig[conv.status]?.color || 'bg-gray-100 text-gray-600'
                      }`}
                    >
                      {statusConfig[conv.status]?.label || conv.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600 text-center">
                    {conv.message_count}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600 text-center">
                    {conv.token_count > 1000
                      ? `${(conv.token_count / 1000).toFixed(1)}K`
                      : conv.token_count}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {conv.updated_at
                      ? new Date(conv.updated_at).toLocaleString('zh-CN')
                      : new Date(conv.created_at).toLocaleString('zh-CN')}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <Link
                        to={`/conversations/${conv.id}`}
                        className="px-3 py-1 text-xs text-blue-600 hover:bg-blue-50 rounded-md transition-colors"
                      >
                        查看
                      </Link>
                      <button
                        onClick={() => handleArchive(conv.id, conv.status)}
                        className="px-3 py-1 text-xs text-gray-600 hover:bg-gray-100 rounded-md transition-colors"
                      >
                        {conv.status === 'archived' ? '恢复' : '归档'}
                      </button>
                      <button
                        onClick={() => handleDelete(conv.id, conv.title)}
                        className="px-3 py-1 text-xs text-red-600 hover:bg-red-50 rounded-md transition-colors"
                      >
                        删除
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {/* 分页 */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100 bg-gray-50/50">
            <span className="text-sm text-gray-500">
              共 {total} 条，第 {page}/{totalPages} 页
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setPage(page - 1)}
                disabled={page <= 1}
                className="px-3 py-1 text-sm border border-gray-200 rounded-md hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                上一页
              </button>
              <button
                onClick={() => setPage(page + 1)}
                disabled={page >= totalPages}
                className="px-3 py-1 text-sm border border-gray-200 rounded-md hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                下一页
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
