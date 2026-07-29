import { useEffect, useState, useCallback } from 'react'
import { Loading, Empty } from '../components/ui'
import * as opApi from '../api/operationLogs'

const actionLabels: Record<string, string> = {
  login: '登录',
  register: '注册',
  logout: '登出',
  create: '创建',
  update: '更新',
  delete: '删除',
  archive: '归档',
  restore: '恢复',
  send_message: '发送消息',
  bind_skill: '绑定 Skill',
  unbind_skill: '解绑 Skill',
}

const actionColors: Record<string, string> = {
  login: 'bg-emerald-100 text-emerald-700',
  register: 'bg-blue-100 text-blue-700',
  logout: 'bg-gray-100 text-gray-600',
  create: 'bg-green-100 text-green-700',
  update: 'bg-amber-100 text-amber-700',
  delete: 'bg-red-100 text-red-700',
  archive: 'bg-purple-100 text-purple-700',
  restore: 'bg-cyan-100 text-cyan-700',
  send_message: 'bg-indigo-100 text-indigo-700',
  bind_skill: 'bg-teal-100 text-teal-700',
  unbind_skill: 'bg-orange-100 text-orange-700',
}

function formatAction(action: string): string {
  return actionLabels[action] || action
}

function actionColor(action: string): string {
  return actionColors[action] || 'bg-gray-100 text-gray-600'
}

export default function OperationLogs() {
  const [items, setItems] = useState<opApi.OperationLog[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // 分页
  const [page, setPage] = useState(1)
  const pageSize = 20

  // 筛选条件
  const [filterAction, setFilterAction] = useState('')
  const [filterResourceType, setFilterResourceType] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  const fetchLogs = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const params: opApi.ListOperationLogsParams = {
        page,
        page_size: pageSize,
        action: filterAction || undefined,
        resource_type: filterResourceType || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      }
      const data = await opApi.listOperationLogs(params)
      setItems(data.items)
      setTotal(data.total)
    } catch (e: any) {
      setError(e?.message || '加载失败')
    } finally {
      setLoading(false)
    }
  }, [page, filterAction, filterResourceType, dateFrom, dateTo])

  useEffect(() => {
    fetchLogs()
  }, [fetchLogs])

  const totalPages = Math.ceil(total / pageSize)

  const handleFilter = () => {
    setPage(1)
    fetchLogs()
  }

  const handleReset = () => {
    setFilterAction('')
    setFilterResourceType('')
    setDateFrom('')
    setDateTo('')
    setPage(1)
  }

  const handleExport = () => {
    const headers = ['时间', '用户ID', '操作', '资源类型', '资源ID', '详情', 'IP地址']
    const rows = items.map(log => [
      log.created_at,
      log.user_id,
      formatAction(log.action),
      log.resource_type,
      log.resource_id || '',
      log.detail || '',
      log.ip_address || '',
    ])
    const csv = [headers.join(','), ...rows.map(r => r.map(v => `"${v}"`).join(','))].join('\n')
    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `operation-logs-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">操作日志</h1>
          <p className="text-sm text-gray-500 mt-1">
            查看系统操作审计日志，支持多维度筛选
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-500">共 {total} 条记录</span>
          <button
            onClick={handleExport}
            disabled={items.length === 0}
            className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50"
          >
            导出 CSV
          </button>
        </div>
      </div>

      {/* 筛选栏 */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500 font-medium">操作类型</label>
            <select
              value={filterAction}
              onChange={(e) => setFilterAction(e.target.value)}
              className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white text-gray-700 focus:outline-none focus:border-blue-400"
            >
              <option value="">全部</option>
              {Object.entries(actionLabels).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500 font-medium">资源类型</label>
            <input
              value={filterResourceType}
              onChange={(e) => setFilterResourceType(e.target.value)}
              placeholder="全部"
              className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white text-gray-700 focus:outline-none focus:border-blue-400 w-32"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500 font-medium">开始日期</label>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white text-gray-700 focus:outline-none focus:border-blue-400"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500 font-medium">结束日期</label>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white text-gray-700 focus:outline-none focus:border-blue-400"
            />
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

      {/* 数据表格 */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loading />
          </div>
        ) : items.length === 0 ? (
          <div className="flex items-center justify-center py-16">
            <Empty title="暂无操作日志" />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50/50">
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">时间</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">用户</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">操作</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">资源类型</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">资源 ID</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">详情</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">IP 地址</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {items.map((log) => (
                  <tr key={log.id} className="hover:bg-gray-50/50 transition-colors">
                    <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                      {new Date(log.created_at).toLocaleString('zh-CN')}
                    </td>
                    <td className="px-4 py-3 text-gray-700 font-mono text-xs">
                      {log.user_id.slice(0, 8)}...
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${actionColor(log.action)}`}>
                        {formatAction(log.action)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-600">{log.resource_type}</td>
                    <td className="px-4 py-3 text-gray-400 font-mono text-xs max-w-[120px] truncate">
                      {log.resource_id || '-'}
                    </td>
                    <td className="px-4 py-3 text-gray-600 max-w-[240px] truncate">
                      {log.detail || '-'}
                    </td>
                    <td className="px-4 py-3 text-gray-400 font-mono text-xs">
                      {log.ip_address || '-'}
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
                className="px-3 py-1 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                上一页
              </button>
              {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
                const start = Math.max(1, page - 2)
                const p = start + i
                if (p > totalPages) return null
                return (
                  <button
                    key={p}
                    onClick={() => setPage(p)}
                    className={`w-8 h-8 text-sm rounded-lg ${
                      p === page
                        ? 'bg-blue-600 text-white'
                        : 'border border-gray-200 hover:bg-gray-50'
                    }`}
                  >
                    {p}
                  </button>
                )
              })}
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="px-3 py-1 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
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
