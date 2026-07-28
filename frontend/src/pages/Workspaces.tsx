import { useEffect, useState } from 'react'
import { useWorkspaceStore } from '../stores/workspaceStore'
import type { WorkspaceCreatePayload, WorkspaceUpdatePayload } from '../api/workspaces'
import { Loading, Empty, ErrorBlock, Pagination } from '../components/ui'

export default function Workspaces() {
  const { items, total, page, pageSize, loading, error, fetch, create, update, remove, setSearch, setPage } = useWorkspaceStore()
  const [searchInput, setSearchInput] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [editing, setEditing] = useState<string | null>(null)
  const [form, setForm] = useState<WorkspaceCreatePayload & { is_active?: boolean }>({ name: '', description: '' })
  const [formError, setFormError] = useState('')

  useEffect(() => { fetch() }, [])

  const totalPages = Math.ceil(total / pageSize)

  const handleSearch = () => setSearch(searchInput)
  const handleKeyDown = (e: React.KeyboardEvent) => { if (e.key === 'Enter') handleSearch() }

  const openCreate = () => {
    setEditing(null)
    setForm({ name: '', description: '' })
    setFormError('')
    setShowModal(true)
  }

  const openEdit = (ws: (typeof items)[0]) => {
    setEditing(ws.id)
    setForm({ name: ws.name, description: ws.description, is_active: ws.is_active })
    setFormError('')
    setShowModal(true)
  }

  const handleDelete = async (id: string, name: string) => {
    if (!window.confirm(`确定要删除工作空间「${name}」吗？`)) return
    await remove(id)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError('')
    try {
      if (editing) {
        await update(editing, form as WorkspaceUpdatePayload)
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
        <div><h1 className="text-2xl font-bold text-gray-900">工作空间</h1><p className="text-gray-500 mt-1">管理工作空间和团队隔离</p></div>
        <button onClick={openCreate} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-2">
          <span>+</span><span>创建工作空间</span>
        </button>
      </div>

      {/* 筛选 */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <div className="flex flex-wrap gap-4 items-center">
          <div className="flex-1 min-w-[200px]">
            <input type="text" value={searchInput} onChange={(e) => setSearchInput(e.target.value)} onKeyDown={handleKeyDown}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none text-sm" placeholder="搜索工作空间..." />
          </div>
          <button onClick={handleSearch} className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm transition-colors">搜索</button>
        </div>
      </div>

      {/* 错误 */}
      {error && <ErrorBlock message={error} onRetry={() => fetch()} />}

      {/* 表格 */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {loading && items.length === 0 ? (
          <Loading fullPage text="加载工作空间列表..." />
        ) : items.length === 0 ? (
          <Empty icon="📁" title="暂无工作空间" description="还没有创建任何工作空间" action={
            <button onClick={openCreate} className="text-blue-600 hover:text-blue-700 text-sm font-medium">创建第一个工作空间</button>
          } />
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50/50">
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">名称</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">描述</th>
                <th className="text-center px-4 py-3 text-sm font-medium text-gray-500">成员数</th>
                <th className="text-center px-4 py-3 text-sm font-medium text-gray-500">状态</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">创建时间</th>
                <th className="text-right px-4 py-3 text-sm font-medium text-gray-500">操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map((ws) => (
                <tr key={ws.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">{ws.name}</td>
                  <td className="px-4 py-3 text-sm text-gray-500 truncate max-w-[200px]">{ws.description || '-'}</td>
                  <td className="px-4 py-3 text-sm text-gray-600 text-center">{ws.member_count}</td>
                  <td className="px-4 py-3 text-center">
                    <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium ${ws.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                      {ws.is_active ? '活跃' : '已禁用'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">{new Date(ws.created_at).toLocaleDateString('zh-CN')}</td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button onClick={() => openEdit(ws)} className="px-3 py-1 text-xs text-blue-600 hover:bg-blue-50 rounded-md">编辑</button>
                      <button onClick={() => handleDelete(ws.id, ws.name)} className="px-3 py-1 text-xs text-red-600 hover:bg-red-50 rounded-md">删除</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {/* 分页 */}
        {totalPages > 1 && !loading && (
          <div className="border-t border-gray-100 px-4 py-3 bg-gray-50/50">
            <Pagination current={page} total={totalPages} totalItems={total} pageSize={pageSize} onChange={setPage} />
          </div>
        )}
      </div>

      {/* 创建/编辑弹窗 */}
      {showModal && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center" onClick={() => setShowModal(false)}>
          <div className="bg-white rounded-2xl p-6 w-full max-w-md mx-4 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-semibold text-gray-900 mb-4">{editing ? '编辑工作空间' : '创建工作空间'}</h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              {formError && <ErrorBlock message={formError} />}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">名称 *</label>
                <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none" placeholder="工作空间名称" required />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
                <textarea value={form.description || ''} onChange={(e) => setForm({ ...form, description: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none resize-none" rows={3} placeholder="描述此工作空间的用途" />
              </div>
              {editing && (
                <div className="flex items-center gap-2">
                  <input type="checkbox" id="is_active" checked={form.is_active ?? true}
                    onChange={(e) => setForm({ ...form, is_active: e.target.checked })} className="rounded border-gray-300" />
                  <label htmlFor="is_active" className="text-sm text-gray-700">启用</label>
                </div>
              )}
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
