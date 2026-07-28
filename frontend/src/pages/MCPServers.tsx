import { useEffect, useState } from 'react'
import { useMCPServerStore } from '../stores/mcpServerStore'
import type { MCPServerCreatePayload, MCPServerUpdatePayload } from '../api/mcps'
import { Loading, Empty, ErrorBlock, Pagination } from '../components/ui'

const statusConfig: Record<string, { label: string; color: string }> = {
  online: { label: '在线', color: 'bg-green-100 text-green-700' },
  offline: { label: '离线', color: 'bg-gray-100 text-gray-600' },
  error: { label: '异常', color: 'bg-red-100 text-red-700' },
}

const healthConfig: Record<string, { label: string; color: string }> = {
  healthy: { label: '健康', color: 'bg-green-100 text-green-700' },
  unhealthy: { label: '不健康', color: 'bg-red-100 text-red-700' },
  unknown: { label: '未知', color: 'bg-gray-100 text-gray-500' },
}

const protocolOptions = ['sse', 'stdio', 'streamable-http']

export default function MCPServers() {
  const { items, total, page, pageSize, loading, error, fetch, create, update, remove, healthCheck, setSearch, setStatusFilter, setPage } = useMCPServerStore()
  const [searchInput, setSearchInput] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [editing, setEditing] = useState<string | null>(null)
  const [form, setForm] = useState<MCPServerCreatePayload>({
    name: '', endpoint: '', protocol: 'sse', description: '', api_key: '',
  })
  const [formError, setFormError] = useState('')

  useEffect(() => { fetch() }, [])

  const totalPages = Math.ceil(total / pageSize)

  const handleSearch = () => setSearch(searchInput)
  const handleKeyDown = (e: React.KeyboardEvent) => { if (e.key === 'Enter') handleSearch() }

  const openCreate = () => {
    setEditing(null)
    setForm({ name: '', endpoint: '', protocol: 'sse', description: '', api_key: '' })
    setFormError('')
    setShowModal(true)
  }

  const openEdit = (s: (typeof items)[0]) => {
    setEditing(s.id)
    setForm({ name: s.name, endpoint: s.endpoint, protocol: s.protocol, description: s.description, api_key: '' })
    setFormError('')
    setShowModal(true)
  }

  const handleDelete = async (id: string, name: string) => {
    if (!window.confirm(`确定要删除 MCP 服务「${name}」吗？`)) return
    await remove(id)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError('')
    try {
      const payload: any = { ...form }
      if (!payload.api_key) payload.api_key = null
      if (editing) {
        await update(editing, payload as MCPServerUpdatePayload)
      } else {
        await create(payload as MCPServerCreatePayload)
      }
      setShowModal(false)
    } catch (err: any) {
      setFormError(err?.response?.data?.detail || '保存失败')
    }
  }

  const statusTabs = [
    { value: '', label: '全部' },
    { value: 'online', label: '在线' },
    { value: 'offline', label: '离线' },
    { value: 'error', label: '异常' },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div><h1 className="text-2xl font-bold text-gray-900">MCP 服务</h1><p className="text-gray-500 mt-1">管理和监控 MCP 服务连接</p></div>
        <button onClick={openCreate} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-2">
          <span>+</span><span>添加 MCP 服务</span>
        </button>
      </div>

      <div className="flex gap-1 bg-gray-100 p-1 rounded-lg w-fit">
        {statusTabs.map((tab) => (
          <button key={tab.value} onClick={() => setStatusFilter(tab.value)}
            className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors ${(useMCPServerStore.getState().statusFilter || '') === tab.value ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}>
            {tab.label}
          </button>
        ))}
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <div className="flex flex-wrap gap-4 items-center">
          <div className="flex-1 min-w-[200px]">
            <input type="text" value={searchInput} onChange={(e) => setSearchInput(e.target.value)} onKeyDown={handleKeyDown}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none text-sm" placeholder="搜索服务名称或 URL..." />
          </div>
          <button onClick={handleSearch} className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm transition-colors">搜索</button>
        </div>
      </div>

      {error && <ErrorBlock message={error} onRetry={() => fetch()} />}

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {loading && items.length === 0 ? (
          <Loading fullPage text="加载 MCP 服务列表..." />
        ) : items.length === 0 ? (
          <Empty icon="🔌" title="暂无 MCP 服务" description="还没有添加任何 MCP 服务" action={
            <button onClick={openCreate} className="text-blue-600 hover:text-blue-700 text-sm font-medium">添加第一个 MCP 服务</button>
          } />
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50/50">
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">名称</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">终端地址</th>
                <th className="text-center px-4 py-3 text-sm font-medium text-gray-500">协议</th>
                <th className="text-center px-4 py-3 text-sm font-medium text-gray-500">状态</th>
                <th className="text-center px-4 py-3 text-sm font-medium text-gray-500">健康状态</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">版本</th>
                <th className="text-right px-4 py-3 text-sm font-medium text-gray-500">操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map((s) => {
                const stCfg = statusConfig[s.status] || { label: s.status, color: 'bg-gray-100 text-gray-600' }
                const hCfg = healthConfig[s.health_status] || { label: s.health_status, color: 'bg-gray-100 text-gray-500' }
                return (
                  <tr key={s.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3">
                      <div className="text-sm font-medium text-gray-900">{s.name}</div>
                      {s.description && <div className="text-xs text-gray-400 truncate max-w-[160px]">{s.description}</div>}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500 font-mono truncate max-w-[200px]">{s.endpoint}</td>
                    <td className="px-4 py-3 text-center"><span className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-purple-50 text-purple-600">{s.protocol}</span></td>
                    <td className="px-4 py-3 text-center"><span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium ${stCfg.color}`}>{stCfg.label}</span></td>
                    <td className="px-4 py-3 text-center"><span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium ${hCfg.color}`}>{hCfg.label}</span></td>
                    <td className="px-4 py-3 text-sm text-gray-600">{s.version || '-'}</td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button onClick={() => healthCheck(s.id)} className="px-3 py-1 text-xs text-gray-600 hover:bg-gray-100 rounded-md" title="运行健康检查">检查</button>
                        <button onClick={() => openEdit(s)} className="px-3 py-1 text-xs text-blue-600 hover:bg-blue-50 rounded-md">编辑</button>
                        <button onClick={() => handleDelete(s.id, s.name)} className="px-3 py-1 text-xs text-red-600 hover:bg-red-50 rounded-md">删除</button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}

        {totalPages > 1 && !loading && (
          <div className="border-t border-gray-100 px-4 py-3 bg-gray-50/50">
            <Pagination current={page} total={totalPages} totalItems={total} pageSize={pageSize} onChange={setPage} />
          </div>
        )}
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center" onClick={() => setShowModal(false)}>
          <div className="bg-white rounded-2xl p-6 w-full max-w-lg mx-4 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-semibold text-gray-900 mb-4">{editing ? '编辑 MCP 服务' : '添加 MCP 服务'}</h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              {formError && <ErrorBlock message={formError} />}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">名称 *</label>
                  <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" required />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">协议</label>
                  <select value={form.protocol || 'sse'} onChange={(e) => setForm({ ...form, protocol: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm">
                    {protocolOptions.map((p) => <option key={p} value={p}>{p.toUpperCase()}</option>)}
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">终端地址 *</label>
                <input type="url" value={form.endpoint} onChange={(e) => setForm({ ...form, endpoint: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" placeholder="https://example.com/mcp" required />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
                <textarea value={form.description || ''} onChange={(e) => setForm({ ...form, description: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm resize-none" rows={2} />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  API Key {editing && <span className="text-gray-400 font-normal">(留空保持原有值)</span>}
                </label>
                <input type="password" value={form.api_key || ''} onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" placeholder={editing ? '留空则不修改' : '可选'} />
              </div>
              <div className="flex gap-3 justify-end pt-2">
                <button type="button" onClick={() => setShowModal(false)} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">取消</button>
                <button type="submit" className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium">{editing ? '保存' : '创建'}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
