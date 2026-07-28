import { useEffect, useState } from 'react'
import { useModelConfigStore } from '../stores/modelConfigStore'
import type { ModelConfigCreatePayload, ModelConfigUpdatePayload } from '../api/models'
import { PROVIDERS } from '../api/models'
import { Loading, Empty, ErrorBlock, Pagination } from '../components/ui'

const defaultForm = {
  name: '',
  provider: 'openai',
  model_name: '',
  endpoint: '',
  api_key: '',
  temperature: 0.7,
  max_tokens: null as number | null,
  context_window: null as number | null,
  embedding_model: '',
  is_default: false,
  description: '',
}

export default function Models() {
  const { items, total, page, pageSize, loading, error, fetch, create, update, remove, testConnection, setSearch, setProviderFilter, setPage } = useModelConfigStore()
  const [searchInput, setSearchInput] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [editing, setEditing] = useState<string | null>(null)
  const [form, setForm] = useState<ModelConfigCreatePayload & { [k: string]: any }>({ ...defaultForm })
  const [formError, setFormError] = useState('')
  const [testing, setTesting] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<string | null>(null)

  useEffect(() => { fetch() }, [])

  const totalPages = Math.ceil(total / pageSize)

  const handleSearch = () => setSearch(searchInput)
  const handleKeyDown = (e: React.KeyboardEvent) => { if (e.key === 'Enter') handleSearch() }

  const openCreate = () => {
    setEditing(null)
    setForm({ ...defaultForm })
    setFormError('')
    setTestResult(null)
    setShowModal(true)
  }

  const openEdit = (m: (typeof items)[0]) => {
    setEditing(m.id)
    setForm({
      name: m.name,
      provider: m.provider,
      model_name: m.model_name,
      endpoint: m.endpoint || '',
      api_key: '',
      temperature: m.temperature ?? 0.7,
      max_tokens: m.max_tokens,
      context_window: m.context_window,
      embedding_model: m.embedding_model || '',
      is_default: m.is_default,
      description: m.description || '',
    })
    setFormError('')
    setTestResult(null)
    setShowModal(true)
  }

  const handleDelete = async (id: string, name: string) => {
    if (!window.confirm(`确定要删除模型配置「${name}」吗？`)) return
    await remove(id)
  }

  const handleTest = async (id: string) => {
    setTesting(id)
    setTestResult(null)
    try {
      const res = await testConnection(id)
      if (res.success) {
        setTestResult(`✅ 连接成功 (${res.latency_ms}ms, 模型: ${res.model})`)
      } else {
        setTestResult(`❌ ${res.error || '连接失败'}`)
      }
    } catch (err: any) {
      setTestResult(`❌ ${err?.response?.data?.detail || err.message || '测试请求失败'}`)
    } finally {
      setTesting(null)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError('')
    setTestResult(null)
    try {
      const payload: any = { ...form }
      // 清除空字符串字段
      if (!payload.endpoint) payload.endpoint = null
      if (!payload.api_key) payload.api_key = null
      if (!payload.embedding_model) payload.embedding_model = null
      if (!payload.description) payload.description = null

      if (editing) {
        await update(editing, payload as ModelConfigUpdatePayload)
      } else {
        await create(payload as ModelConfigCreatePayload)
      }
      setShowModal(false)
    } catch (err: any) {
      setFormError(err?.response?.data?.detail || '保存失败')
    }
  }

  const providerMap = Object.fromEntries(PROVIDERS.filter(p => p.value).map(p => [p.value, p.label]))

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div><h1 className="text-2xl font-bold text-gray-900">模型配置</h1><p className="text-gray-500 mt-1">管理模型 Provider 和参数模板</p></div>
        <button onClick={openCreate} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-2">
          <span>+</span><span>添加模型配置</span>
        </button>
      </div>

      {testResult && (
        <div className={`px-4 py-3 rounded-lg border text-sm ${testResult.startsWith('✅') ? 'bg-green-50 border-green-200 text-green-700' : 'bg-red-50 border-red-200 text-red-600'}`}>
          {testResult}
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <div className="flex flex-wrap gap-4 items-center">
          <div className="flex-1 min-w-[200px]">
            <input type="text" value={searchInput} onChange={(e) => setSearchInput(e.target.value)} onKeyDown={handleKeyDown}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none text-sm" placeholder="搜索名称或模型..." />
          </div>
          <button onClick={handleSearch} className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm transition-colors">搜索</button>
          <select value={useModelConfigStore.getState().providerFilter} onChange={(e) => setProviderFilter(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500">
            {PROVIDERS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
        </div>
      </div>

      {error && <ErrorBlock message={error} onRetry={() => fetch()} />}

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {loading && items.length === 0 ? (
          <Loading fullPage text="加载模型配置..." />
        ) : items.length === 0 ? (
          <Empty icon="🧠" title="暂无模型配置" description="还没有添加任何模型配置" action={
            <button onClick={openCreate} className="text-blue-600 hover:text-blue-700 text-sm font-medium">添加第一个模型配置</button>
          } />
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50/50">
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">名称</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">Provider</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">模型</th>
                <th className="text-center px-4 py-3 text-sm font-medium text-gray-500">默认</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">创建时间</th>
                <th className="text-right px-4 py-3 text-sm font-medium text-gray-500">操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map((m) => (
                <tr key={m.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3">
                    <div className="text-sm font-medium text-gray-900">{m.name}</div>
                    {m.description && <div className="text-xs text-gray-400 truncate max-w-[180px]">{m.description}</div>}
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-600">
                      {providerMap[m.provider] || m.provider}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600 font-mono">{m.model_name}</td>
                  <td className="px-4 py-3 text-center">
                    {m.is_default ? <span className="text-green-600 font-medium text-sm">✓ 默认</span> : <span className="text-gray-300 text-sm">—</span>}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">{new Date(m.created_at).toLocaleDateString('zh-CN')}</td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button onClick={() => handleTest(m.id)} disabled={testing === m.id}
                        className="px-3 py-1 text-xs text-gray-600 hover:bg-gray-100 rounded-md disabled:opacity-50">
                        {testing === m.id ? '测试中...' : '测试'}
                      </button>
                      <button onClick={() => openEdit(m)} className="px-3 py-1 text-xs text-blue-600 hover:bg-blue-50 rounded-md">编辑</button>
                      <button onClick={() => handleDelete(m.id, m.name)} className="px-3 py-1 text-xs text-red-600 hover:bg-red-50 rounded-md">删除</button>
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

      {/* 创建/编辑弹窗 */}
      {showModal && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center" onClick={() => setShowModal(false)}>
          <div className="bg-white rounded-2xl p-6 w-full max-w-2xl mx-4 shadow-xl max-h-[85vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-semibold text-gray-900 mb-4">{editing ? '编辑模型配置' : '添加模型配置'}</h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              {formError && <ErrorBlock message={formError} />}

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">名称 *</label>
                  <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" required />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Provider *</label>
                  <select value={form.provider} onChange={(e) => setForm({ ...form, provider: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm">
                    {PROVIDERS.filter(p => p.value).map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
                  </select>
                </div>
                <div className="col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1">模型名称 *</label>
                  <input type="text" value={form.model_name} onChange={(e) => setForm({ ...form, model_name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" placeholder="如 gpt-4o, deepseek-chat, qwen-turbo" required />
                </div>
                <div className="col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1">API Endpoint</label>
                  <input type="url" value={form.endpoint || ''} onChange={(e) => setForm({ ...form, endpoint: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" placeholder="可选，默认使用 Provider 的官方地址" />
                </div>
                <div className="col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1">API Key {editing && <span className="text-gray-400 font-normal">(留空保持原有值)</span>}</label>
                  <input type="password" value={form.api_key || ''} onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" placeholder={editing ? '留空则不修改' : '请输入 API Key'} />
                </div>
              </div>

              <div className="border-t border-gray-100 pt-4">
                <h3 className="text-sm font-medium text-gray-700 mb-3">参数配置</h3>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-600 mb-1">Temperature</label>
                    <input type="number" step="0.1" min="0" max="2" value={form.temperature ?? 0.7} onChange={(e) => setForm({ ...form, temperature: parseFloat(e.target.value) || 0 })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-600 mb-1">Max Tokens</label>
                    <input type="number" step="1" min="0" value={form.max_tokens ?? ''} onChange={(e) => setForm({ ...form, max_tokens: e.target.value ? parseInt(e.target.value) : null })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" placeholder="默认" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-600 mb-1">Context Window</label>
                    <input type="number" step="1" min="0" value={form.context_window ?? ''} onChange={(e) => setForm({ ...form, context_window: e.target.value ? parseInt(e.target.value) : null })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" placeholder="默认" />
                  </div>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Embedding 模型</label>
                <input type="text" value={form.embedding_model || ''} onChange={(e) => setForm({ ...form, embedding_model: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" placeholder="可选，用于 RAG 的 embedding 模型" />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
                <textarea value={form.description || ''} onChange={(e) => setForm({ ...form, description: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm resize-none" rows={2} placeholder="可选备注" />
              </div>

              <div className="flex items-center gap-2">
                <input type="checkbox" id="is_default" checked={form.is_default ?? false}
                  onChange={(e) => setForm({ ...form, is_default: e.target.checked })} className="rounded border-gray-300" />
                <label htmlFor="is_default" className="text-sm text-gray-700">设为默认模型配置</label>
              </div>

              <div className="flex gap-3 justify-end pt-2 border-t border-gray-100">
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
