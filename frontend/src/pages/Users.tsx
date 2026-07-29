import { useEffect, useState, useCallback } from 'react'
import { Loading, Empty } from '../components/ui'
import * as userApi from '../api/users'

const roleLabels: Record<string, string> = {
  admin: '管理员',
  developer: '开发者',
  user: '普通用户',
  guest: '访客',
}

const roleColors: Record<string, string> = {
  admin: 'bg-red-100 text-red-700',
  developer: 'bg-blue-100 text-blue-700',
  user: 'bg-green-100 text-green-700',
  guest: 'bg-gray-100 text-gray-600',
}

export default function Users() {
  const [items, setItems] = useState<userApi.User[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // 分页
  const [page, setPage] = useState(1)
  const pageSize = 20

  // 筛选
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [activeFilter, setActiveFilter] = useState('')

  // 编辑弹窗
  const [editingUser, setEditingUser] = useState<userApi.User | null>(null)
  const [editRole, setEditRole] = useState('')
  const [editActive, setEditActive] = useState(true)
  const [saving, setSaving] = useState(false)

  const fetchUsers = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const params: any = { page, page_size: pageSize }
      if (search) params.search = search
      if (roleFilter) params.role = roleFilter
      if (activeFilter) params.is_active = activeFilter === 'active'
      const data = await userApi.listUsers(params)
      setItems(data.items)
      setTotal(data.total)
    } catch (e: any) {
      setError(e?.message || '加载失败')
    } finally {
      setLoading(false)
    }
  }, [page, search, roleFilter, activeFilter])

  useEffect(() => {
    fetchUsers()
  }, [fetchUsers])

  const totalPages = Math.ceil(total / pageSize)

  const handleFilter = () => { setPage(1); fetchUsers() }
  const handleReset = () => { setSearch(''); setRoleFilter(''); setActiveFilter(''); setPage(1) }

  const openEdit = (user: userApi.User) => {
    setEditingUser(user)
    setEditRole(user.role)
    setEditActive(user.is_active)
  }

  const handleSave = async () => {
    if (!editingUser) return
    setSaving(true)
    try {
      await userApi.updateUser(editingUser.id, { role: editRole, is_active: editActive })
      setEditingUser(null)
      fetchUsers()
    } catch (e: any) {
      alert(e?.message || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (user: userApi.User) => {
    if (!window.confirm(`确定要删除用户「${user.username}」吗？此操作不可恢复。`)) return
    try {
      await userApi.deleteUser(user.id)
      fetchUsers()
    } catch (e: any) {
      alert(e?.message || '删除失败')
    }
  }

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">用户管理</h1>
          <p className="text-sm text-gray-500 mt-1">
            管理系统用户、角色和状态
          </p>
        </div>
        <span className="text-sm text-gray-500">共 {total} 名用户</span>
      </div>

      {/* 筛选栏 */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500 font-medium">搜索</label>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="用户名 / 邮箱 / 显示名"
              className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white text-gray-700 focus:outline-none focus:border-blue-400 w-48"
              onKeyDown={(e) => e.key === 'Enter' && handleFilter()}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500 font-medium">角色</label>
            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white text-gray-700 focus:outline-none focus:border-blue-400"
            >
              <option value="">全部角色</option>
              {Object.entries(roleLabels).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500 font-medium">状态</label>
            <select
              value={activeFilter}
              onChange={(e) => setActiveFilter(e.target.value)}
              className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white text-gray-700 focus:outline-none focus:border-blue-400"
            >
              <option value="">全部</option>
              <option value="active">活跃</option>
              <option value="inactive">已禁用</option>
            </select>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleFilter}
              className="px-4 py-1.5 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
            >
              筛选
            </button>
            <button
              onClick={handleReset}
              className="px-4 py-1.5 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
            >
              重置
            </button>
          </div>
        </div>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="bg-red-50 text-red-600 text-sm px-4 py-3 rounded-lg border border-red-100">
          {error}
        </div>
      )}

      {/* 用户表格 */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-16"><Loading /></div>
        ) : items.length === 0 ? (
          <div className="flex items-center justify-center py-16"><Empty title="暂无用户数据" /></div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50/50">
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">用户名</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">邮箱</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">角色</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">状态</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">最后登录</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">注册时间</th>
                  <th className="text-right px-4 py-3 text-xs font-medium text-gray-500 uppercase">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {items.map((user) => (
                  <tr key={user.id} className="hover:bg-gray-50/50 transition-colors">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-sm font-medium text-blue-700">
                          {(user.display_name || user.username)[0].toUpperCase()}
                        </div>
                        <div>
                          <div className="text-gray-800 font-medium">{user.display_name || user.username}</div>
                          <div className="text-xs text-gray-400">@{user.username}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-600">{user.email}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${roleColors[user.role] || 'bg-gray-100 text-gray-600'}`}>
                        {roleLabels[user.role] || user.role}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1 text-xs ${user.is_active ? 'text-green-600' : 'text-red-500'}`}>
                        <span className={`w-2 h-2 rounded-full ${user.is_active ? 'bg-green-500' : 'bg-red-400'}`} />
                        {user.is_active ? '活跃' : '已禁用'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs">
                      {user.last_login_at ? new Date(user.last_login_at).toLocaleString('zh-CN') : '从未登录'}
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs">
                      {user.created_at ? new Date(user.created_at).toLocaleString('zh-CN') : '-'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => openEdit(user)}
                          className="px-2 py-1 text-xs text-blue-600 hover:bg-blue-50 rounded transition-colors"
                        >
                          编辑
                        </button>
                        <button
                          onClick={() => handleDelete(user)}
                          className="px-2 py-1 text-xs text-red-600 hover:bg-red-50 rounded transition-colors"
                        >
                          删除
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* 分页 */}
        {totalPages > 1 && (
          <div className="border-t border-gray-100 px-4 py-3 flex items-center justify-between">
            <span className="text-sm text-gray-500">
              第 {page} / {totalPages} 页，共 {total} 条
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="px-3 py-1 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50"
              >上一页</button>
              {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
                const start = Math.max(1, page - 2)
                const p = start + i
                if (p > totalPages) return null
                return (
                  <button key={p} onClick={() => setPage(p)}
                    className={`w-8 h-8 text-sm rounded-lg ${p === page ? 'bg-blue-600 text-white' : 'border border-gray-200 hover:bg-gray-50'}`}
                  >{p}</button>
                )
              })}
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="px-3 py-1 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50"
              >下一页</button>
            </div>
          </div>
        )}
      </div>

      {/* 编辑弹窗 */}
      {editingUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={() => setEditingUser(null)}>
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md mx-4" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              编辑用户 — {editingUser.display_name || editingUser.username}
            </h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">角色</label>
                <select
                  value={editRole}
                  onChange={(e) => setEditRole(e.target.value)}
                  className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white text-gray-700 focus:outline-none focus:border-blue-400"
                >
                  {Object.entries(roleLabels).map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="flex items-center gap-2 text-sm font-medium text-gray-700">
                  <input
                    type="checkbox"
                    checked={editActive}
                    onChange={(e) => setEditActive(e.target.checked)}
                    className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  账号活跃
                </label>
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-6">
              <button
                onClick={() => setEditingUser(null)}
                className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
              >取消</button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-50"
              >{saving ? '保存中...' : '保存'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
