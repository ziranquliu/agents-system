import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useConversationStore } from '../stores/conversationStore'
import { useAgentStore } from '../stores/agentStore'
import { Loading, Empty, ErrorBlock, Pagination } from '../components/ui'

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

  const handleSearch = () => setSearch(searchInput)
  const handleKeyDown = (e: React.KeyboardEvent) => { if (e.key === 'Enter') handleSearch() }

  const handleDelete = async (id: string, title: string) => {
    if (!window.confirm(`确定要删除对话「${title || '未命名对话'}」吗？`)) return
    await deleteConversation(id)
  }

  const handleArchive = async (id: string, currentStatus: string) => {
    try { await updateStatus(id, currentStatus === 'archived' ? 'active' : 'archived') } 
    catch { window.alert('操作失败') }
  }

  const agentMap = new Map(agents.map((a) => [a.id, a.name]))

  const tabs = [
    { value: '', label: '全部' },
    { value: 'active', label: '活跃' },
    { value: 'archived', label: '已归档' },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">对话管理</h1>
        <p className="text-gray-500 mt-1">查看和管理所有对话历史</p>
      </div>

      <div className="flex gap-1 bg-gray-100 p-1 rounded-lg w-fit">
        {tabs.map((tab) => (
          <button key={tab.value} onClick={() => { setStatusTab(tab.value); setStatusFilter(tab.value) }}
            className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors ${(statusTab || '') === tab.value ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}>
            {tab.label}
          </button>
        ))}
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <div className="flex flex-wrap gap-4 items-center">
          <div className="flex-1 min-w-[200px]">
            <input type="text" value={searchInput} onChange={(e) => setSearchInput(e.target.value)} onKeyDown={handleKeyDown}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none text-sm" placeholder="搜索对话标题..." />
          </div>
          <button onClick={handleSearch} className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm transition-colors">搜索</button>
        </div>
      </div>

      {error && <ErrorBlock message={error} onRetry={() => fetchConversations()} />}

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {loading && conversations.length === 0 ? (
          <Loading fullPage text="加载对话列表..." />
        ) : conversations.length === 0 ? (
          <Empty icon="💬" title="暂无对话记录" description="当用户与 Agent 开始对话后，记录将出现在这里" />
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
                <tr key={conv.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3">
                    <Link to={`/conversations/${conv.id}`} className="text-sm font-medium text-blue-600 hover:text-blue-700">{conv.title || '未命名对话'}</Link>
                    {conv.summary && <p className="text-xs text-gray-400 mt-0.5 truncate max-w-[240px]">{conv.summary}</p>}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">{agentMap.get(conv.agent_id) || conv.agent_id.slice(0, 8) + '...'}</td>
                  <td className="px-4 py-3"><span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium ${statusConfig[conv.status]?.color || 'bg-gray-100 text-gray-600'}`}>{statusConfig[conv.status]?.label || conv.status}</span></td>
                  <td className="px-4 py-3 text-sm text-gray-600 text-center">{conv.message_count}</td>
                  <td className="px-4 py-3 text-sm text-gray-600 text-center">{conv.token_count > 1000 ? `${(conv.token_count / 1000).toFixed(1)}K` : conv.token_count}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">{new Date(conv.updated_at || conv.created_at).toLocaleString('zh-CN')}</td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <Link to={`/conversations/${conv.id}`} className="px-3 py-1 text-xs text-blue-600 hover:bg-blue-50 rounded-md">查看</Link>
                      <button onClick={() => handleArchive(conv.id, conv.status)} className="px-3 py-1 text-xs text-gray-600 hover:bg-gray-100 rounded-md">{conv.status === 'archived' ? '恢复' : '归档'}</button>
                      <button onClick={() => handleDelete(conv.id, conv.title)} className="px-3 py-1 text-xs text-red-600 hover:bg-red-50 rounded-md">删除</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {totalPages > 1 && !loading && (
          <div className="border-t border-gray-100 px-4 py-3 bg-gray-50/50">
            <Pagination current={page} total={totalPages} totalItems={total} pageSize={pageSize} onChange={setPage} />
          </div>
        )}
      </div>
    </div>
  )
}
