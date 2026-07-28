import { useEffect, useState } from 'react'
import { useSkillStore } from '../stores/skillStore'
import type { SkillCreatePayload, SkillUpdatePayload } from '../api/skills'
import { Loading, Empty, ErrorBlock, Pagination } from '../components/ui'

const typeOptions = [
  { value: '', label: '全部类型' },
  { value: 'tool', label: '工具' },
  { value: 'skill', label: '技能' },
  { value: 'plugin', label: '插件' },
]

export default function Skills() {
  const { items, total, page, pageSize, loading, error, fetch, create, update, remove, toggleEnabled, setSearch, setTypeFilter, setPage } = useSkillStore()
  const [searchInput, setSearchInput] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [editing, setEditing] = useState<string | null>(null)
  const [form, setForm] = useState<SkillCreatePayload>({ name: '', version: '1.0.0', description: '', type: 'skill', category: '', entry_point: '', enabled: true })
  const [formError, setFormError] = useState('')

  useEffect(() => { fetch() }, [])

  const totalPages = Math.ceil(total / pageSize)

  const handleSearch = () => setSearch(searchInput)
  const handleKeyDown = (e: React.KeyboardEvent) => { if (e.key === 'Enter') handleSearch() }

  const openCreate = () => {
    setEditing(null)
    setForm({ name: '', version: '1.0.0', description: '', type: 'skill', category: '', entry_point: '', enabled: true })
    setFormError('')
    setShowModal(true)
  }

  const openEdit = (s: (typeof items)[0]) => {
    setEditing(s.id)
    setForm({ name: s.name, version: s.version, description: s.description, type: s.type || 'skill', category: s.category || '', entry_point: s.entry_point, enabled: s.enabled })
    setFormError('')
    setShowModal(true)
  }

  const handleDelete = async (id: string, name: string) => {
    if (!window.confirm(`确定要删除技能「${name}」吗？`)) return
    await remove(id)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError('')
    try {
      if (editing) {
        await update(editing, form as SkillUpdatePayload)
      } else {
        await create(form)
      }
      setShowModal(false)
    } catch (err: any) {
      setFormError(err?.response?.data?.detail || '保存失败')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div><h1 className="text-2xl font-bold text-gray-900">Skill 管理</h1><p className="text-gray-500 mt-1">管理和配置 Agent 技能</p></div>
        <button onClick={openCreate} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-2">
          <span>+</span><span>创建 Skill</span>
        </button>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <div className="flex flex-wrap gap-4 items-center">
          <div className="flex-1 min-w-[200px]">
            <input type="text" value={searchInput} onChange={(e) => setSearchInput(e.target.value)} onKeyDown={handleKeyDown}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none text-sm" placeholder="搜索技能名称..." />
          </div>
          <button onClick={handleSearch} className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm transition-colors">搜索</button>
          <select value={useSkillStore.getState().typeFilter} onChange={(e) => setTypeFilter(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500">
            {typeOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
      </div>

      {error && <ErrorBlock message={error} onRetry={() => fetch()} />}

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {loading && items.length === 0 ? (
          <Loading fullPage text="加载技能列表..." />
        ) : items.length === 0 ? (
          <Empty icon="🔧" title="暂无 Skill" description="还没有创建任何技能" action={
            <button onClick={openCreate} className="text-blue-600 hover:text-blue-700 text-sm font-medium">创建第一个 Skill</button>
          } />
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50/50">
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">名称</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">版本</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">类型</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">分类</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">来源</th>
                <th className="text-center px-4 py-3 text-sm font-medium text-gray-500">状态</th>
                <th className="text-center px-4 py-3 text-sm font-medium text-gray-500">安装量</th>
                <th className="text-right px-4 py-3 text-sm font-medium text-gray-500">操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map((s) => (
                <tr key={s.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3">
                    <div className="text-sm font-medium text-gray-900">{s.name}</div>
                    {s.description && <div className="text-xs text-gray-400 truncate max-w-[160px]">{s.description}</div>}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">v{s.version}</td>
                  <td className="px-4 py-3"><span className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-600">{s.type || '-'}</span></td>
                  <td className="px-4 py-3 text-sm text-gray-600">{s.category || '-'}</td>
                  <td className="px-4 py-3 text-sm text-gray-600">{s.source === 'marketplace' ? '📦 市场' : '💻 本地'}</td>
                  <td className="px-4 py-3 text-center">
                    <button onClick={() => toggleEnabled(s.id, !s.enabled)}
                      className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium transition-colors ${s.enabled ? 'bg-green-100 text-green-700 hover:bg-green-200' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'}`}>
                      {s.enabled ? '已启用' : '已禁用'}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600 text-center">{s.installed_count}</td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button onClick={() => openEdit(s)} className="px-3 py-1 text-xs text-blue-600 hover:bg-blue-50 rounded-md">编辑</button>
                      <button onClick={() => handleDelete(s.id, s.name)} className="px-3 py-1 text-xs text-red-600 hover:bg-red-50 rounded-md">删除</button>
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

      {showModal && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center" onClick={() => setShowModal(false)}>
          <div className="bg-white rounded-2xl p-6 w-full max-w-lg mx-4 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-semibold text-gray-900 mb-4">{editing ? '编辑 Skill' : '创建 Skill'}</h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              {formError && <ErrorBlock message={formError} />}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">名称 *</label>
                  <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" required />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">版本</label>
                  <input type="text" value={form.version || '1.0.0'} onChange={(e) => setForm({ ...form, version: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">类型</label>
                  <select value={form.type || 'skill'} onChange={(e) => setForm({ ...form, type: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm">
                    <option value="skill">技能</option><option value="tool">工具</option><option value="plugin">插件</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">分类</label>
                  <input type="text" value={form.category || ''} onChange={(e) => setForm({ ...form, category: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" placeholder="analysis / search / code" />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
                <textarea value={form.description || ''} onChange={(e) => setForm({ ...form, description: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm resize-none" rows={2} />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">入口点</label>
                <input type="text" value={form.entry_point || ''} onChange={(e) => setForm({ ...form, entry_point: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" placeholder="如 src/tools/search.py" />
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
