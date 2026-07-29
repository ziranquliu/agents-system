import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAgentStore } from '../stores/agentStore'
import type { AgentCreatePayload, DiscoveredModel } from '../api/agents'
import { discoverAgents, registerDiscoveredAgent } from '../api/agents'
import { Loading, Empty, ErrorBlock, Pagination } from '../components/ui'

const statusConfig: Record<string, { label: string; color: string }> = {
  draft: { label: '草稿', color: 'bg-gray-100 text-gray-600' },
  running: { label: '运行中', color: 'bg-green-100 text-green-700' },
  stopped: { label: '已停止', color: 'bg-yellow-100 text-yellow-700' },
  error: { label: '异常', color: 'bg-red-100 text-red-700' },
  archived: { label: '已归档', color: 'bg-slate-100 text-slate-600' },
}

const statusOptions = [
  { value: '', label: '全部状态' }, { value: 'draft', label: '草稿' },
  { value: 'running', label: '运行中' }, { value: 'stopped', label: '已停止' },
  { value: 'error', label: '异常' }, { value: 'archived', label: '已归档' },
]

export default function Agents() {
  const navigate = useNavigate()
  const { agents, total, page, pageSize, loading, error, fetchAgents, deleteAgent, setSearch, setStatusFilter, createAgent } = useAgentStore()
  const [searchInput, setSearchInput] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [createForm, setCreateForm] = useState<AgentCreatePayload>({ name: '', description: '', status: 'draft' })
  const [createError, setCreateError] = useState('')
  const [showDiscover, setShowDiscover] = useState(false)
  const [discovered, setDiscovered] = useState<DiscoveredModel[]>([])
  const [discovering, setDiscovering] = useState(false)
  const [discoverError, setDiscoverError] = useState('')
  const [registeringIds, setRegisteringIds] = useState<Set<string>>(new Set())

  useEffect(() => { fetchAgents() }, [])

  const totalPages = Math.ceil(total / pageSize)

  const handleSearch = () => setSearch(searchInput)
  const handleKeyDown = (e: React.KeyboardEvent) => { if (e.key === 'Enter') handleSearch() }

  const handleDelete = async (id: string, name: string) => {
    if (!window.confirm(`确定要删除 Agent「${name}」吗？`)) return
    await deleteAgent(id)
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreateError('')
    try {
      const agent = await createAgent(createForm)
      setShowCreate(false)
      setCreateForm({ name: '', description: '', status: 'draft' })
      navigate(`/agents/${agent.id}`)
    } catch (err: any) {
      setCreateError(err?.response?.data?.detail || '创建失败')
    }
  }

  const handleDiscover = async () => {
    setDiscovering(true)
    setDiscoverError('')
    setShowDiscover(true)
    try {
      const res = await discoverAgents()
      setDiscovered(res.items)
    } catch (err: any) {
      setDiscoverError(err?.response?.data?.detail || '扫描失败，请确认后端已重启')
      setDiscovered([])
    } finally {
      setDiscovering(false)
    }
  }

  const handleRegister = async (model: DiscoveredModel) => {
    setRegisteringIds((prev) => new Set(prev).add(model.model_name))
    try {
      await registerDiscoveredAgent({
        model_name: model.model_name,
        provider: model.provider,
        endpoint: model.endpoint,
      })
      fetchAgents()
    } catch (err: any) {
      alert(err?.response?.data?.detail || '注册失败')
    } finally {
      setRegisteringIds((prev) => { const next = new Set(prev); next.delete(model.model_name); return next })
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Agent 管理</h1>
          <p className="text-gray-500 mt-1">管理所有智能体实例</p>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={handleDiscover} className="px-4 py-2 border border-blue-200 text-blue-600 hover:bg-blue-50 rounded-lg text-sm font-medium transition-colors flex items-center gap-2">
            <span>🔍</span><span>发现本地 Agent</span>
          </button>
          <button onClick={() => setShowCreate(true)} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-2">
            <span>+</span><span>创建 Agent</span>
          </button>
        </div>
      </div>

      {showCreate && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center" onClick={() => setShowCreate(false)}>
          <div className="bg-white rounded-2xl p-6 w-full max-w-lg mx-4 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-semibold text-gray-900 mb-4">创建 Agent</h2>
            <form onSubmit={handleCreate} className="space-y-4">
              {createError && <ErrorBlock message={createError} />}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">名称 *</label>
                <input type="text" value={createForm.name} onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none" placeholder="Agent 名称" required />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
                <textarea value={createForm.description || ''} onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none resize-none" rows={3} placeholder="简要描述此 Agent 的用途" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">初始状态</label>
                <select value={createForm.status} onChange={(e) => setCreateForm({ ...createForm, status: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none">
                  <option value="draft">草稿</option>
                  <option value="running">直接运行</option>
                </select>
              </div>
              <div className="flex gap-3 justify-end pt-2">
                <button type="button" onClick={() => setShowCreate(false)} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">取消</button>
                <button type="submit" className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium">创建</button>
              </div>
            </form>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <div className="flex flex-wrap gap-4 items-center">
          <div className="flex-1 min-w-[200px]">
            <input type="text" value={searchInput} onChange={(e) => setSearchInput(e.target.value)} onKeyDown={handleKeyDown}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none text-sm" placeholder="搜索 Agent 名称..." />
          </div>
          <button onClick={handleSearch} className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm transition-colors">搜索</button>
          <select value={useAgentStore.getState().statusFilter} onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500">
            {statusOptions.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
          </select>
        </div>
      </div>

      {error && <ErrorBlock message={error} onRetry={() => fetchAgents()} />}

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {loading && agents.length === 0 ? (
          <Loading fullPage text="加载 Agent 列表..." />
        ) : agents.length === 0 ? (
          <Empty icon="🤖" title="暂无 Agent" description="还没有创建任何 Agent" action={
            <button onClick={() => setShowCreate(true)} className="text-blue-600 hover:text-blue-700 text-sm font-medium">创建第一个 Agent</button>
          } />
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50/50">
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">名称</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">状态</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">模型</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">提供商</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">创建时间</th>
                <th className="text-right px-4 py-3 text-sm font-medium text-gray-500">操作</th>
              </tr>
            </thead>
            <tbody>
              {agents.map((agent) => (
                <tr key={agent.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3">
                    <Link to={`/agents/${agent.id}`} className="text-sm font-medium text-blue-600 hover:text-blue-700">{agent.name}</Link>
                    {agent.description && <p className="text-xs text-gray-400 mt-0.5 truncate max-w-[200px]">{agent.description}</p>}
                  </td>
                  <td className="px-4 py-3"><span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium ${statusConfig[agent.status]?.color || 'bg-gray-100 text-gray-600'}`}>{statusConfig[agent.status]?.label || agent.status}</span></td>
                  <td className="px-4 py-3 text-sm text-gray-600">{agent.model_name || '-'}</td>
                  <td className="px-4 py-3 text-sm text-gray-600">{agent.model_provider || '-'}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">{new Date(agent.created_at).toLocaleDateString('zh-CN')}</td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <Link to={`/agents/${agent.id}`} className="px-3 py-1 text-xs text-blue-600 hover:bg-blue-50 rounded-md">编辑</Link>
                      <button onClick={() => handleDelete(agent.id, agent.name)} className="px-3 py-1 text-xs text-red-600 hover:bg-red-50 rounded-md">删除</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {totalPages > 1 && !loading && (
          <div className="border-t border-gray-100 px-4 py-3 bg-gray-50/50">
            <Pagination current={page} total={totalPages} totalItems={total} pageSize={pageSize} onChange={(p) => useAgentStore.getState().setPage(p)} />
          </div>
        )}
      </div>
    </div>

    {/* Agent 发现 Modal */}
    {showDiscover && (
      <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => setShowDiscover(false)}>
        <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full max-h-[80vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
          <div className="flex items-center justify-between p-5 border-b border-gray-100">
            <h2 className="text-lg font-semibold text-gray-900">发现本地 Agent</h2>
            <button onClick={() => setShowDiscover(false)} className="text-gray-400 hover:text-gray-600 text-xl leading-none">&times;</button>
          </div>
          <div className="p-5 overflow-y-auto flex-1">
            {discovering ? (
              <div className="flex flex-col items-center gap-3 py-12">
                <div className="w-10 h-10 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin"></div>
                <p className="text-sm text-gray-500">正在扫描本地 AI 服务...</p>
              </div>
            ) : discoverError ? (
              <div className="text-center py-8">
                <p className="text-red-500 text-sm mb-2">{discoverError}</p>
                <p className="text-gray-400 text-xs">请确认已启动 Ollama 服务并重启后端</p>
              </div>
            ) : discovered.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-gray-500 mb-2">未发现本地运行的 AI 模型</p>
                <p className="text-gray-400 text-xs">请启动 Ollama 后重试 (http://localhost:11434)</p>
              </div>
            ) : (
              <div className="space-y-3">
                {discovered.map((m) => (
                  <div key={m.model_name} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">{m.model_name}</p>
                      <div className="flex gap-3 mt-1">
                        <span className="text-xs text-gray-500">{m.provider}</span>
                        <span className="text-xs text-gray-400">|</span>
                        <span className="text-xs text-gray-500 truncate">{m.source_name}</span>
                      </div>
                    </div>
                    <button
                      onClick={() => handleRegister(m)}
                      disabled={registeringIds.has(m.model_name)}
                      className="ml-4 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white text-xs font-medium rounded-lg transition-colors whitespace-nowrap"
                    >
                      {registeringIds.has(m.model_name) ? '注册中...' : '注册为 Agent'}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="p-4 border-t border-gray-100 flex justify-end">
            <button onClick={() => setShowDiscover(false)} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 font-medium">关闭</button>
          </div>
        </div>
      </div>
    )}
  )
}
