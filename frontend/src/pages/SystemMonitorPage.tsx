import React, { useEffect, useState } from 'react'
import { getSystemHealth, getApiLatency, createBackup, listBackups, deleteBackup } from '../api/systemBackup'
import { useToast } from '../components/ui'

const SystemMonitorPage: React.FC = () => {
  const toast = useToast()
  const [health, setHealth] = useState<any>(null)
  const [latency, setLatency] = useState<any>(null)
  const [backups, setBackups] = useState<any[]>([])
  const [backingUp, setBackingUp] = useState(false)

  const loadData = async () => {
    try {
      const [h, l, b] = await Promise.all([
        getSystemHealth(), getApiLatency(), listBackups(),
      ])
      setHealth(h)
      setLatency(l)
      setBackups(b.backups || [])
    } catch { /* ignore */ }
  }

  useEffect(() => { loadData() }, [])

  const handleBackup = async () => {
    setBackingUp(true)
    try {
      const resp = await createBackup()
      toast.success(`备份成功: ${resp.filename}`)
      loadData()
    } catch { toast.error('备份失败') }
    finally { setBackingUp(false) }
  }

  const handleDeleteBackup = async (id: string) => {
    try {
      await deleteBackup(id)
      toast.success('备份已删除')
      loadData()
    } catch { toast.error('删除失败') }
  }

  const statusBadge = (status: string) => {
    const colors: Record<string, string> = {
      healthy: 'bg-green-100 text-green-700',
      warning: 'bg-yellow-100 text-yellow-700',
      critical: 'bg-red-100 text-red-700',
      unavailable: 'bg-gray-100 text-gray-500',
    }
    return <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[status] || 'bg-gray-100'}`}>{status}</span>
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <h1 className="text-2xl font-bold flex items-center gap-2 mb-6">📊 系统监控 & 备份恢复</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 系统健康 */}
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="font-semibold mb-4">🖥️ 系统健康</h2>
          {health ? (
            <div className="space-y-4">
              {['cpu', 'memory', 'disk'].map(comp => {
                const data = health[comp]
                if (!data || data.status === 'unavailable') {
                  return (
                    <div key={comp} className="flex items-center justify-between bg-gray-50 p-3 rounded-lg">
                      <span className="text-sm font-medium uppercase">{comp}</span>
                      <span className="text-xs text-gray-400">{data?.message || '不可用'}</span>
                    </div>
                  )
                }
                return (
                  <div key={comp} className="bg-gray-50 p-3 rounded-lg">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium uppercase">{comp}</span>
                      {statusBadge(data.status)}
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div className={`rounded-full h-2 ${data.usage_percent > 80 ? 'bg-red-500' : data.usage_percent > 60 ? 'bg-yellow-500' : 'bg-green-500'}`}
                        style={{ width: `${Math.min(data.usage_percent || 0, 100)}%` }} />
                    </div>
                    <div className="flex justify-between text-xs text-gray-400 mt-1">
                      <span>{data.usage_percent}% 已用</span>
                      <span>{comp === 'cpu' ? `${data.cores} 核` : `${data.used_gb}/${data.total_gb} GB`}</span>
                    </div>
                  </div>
                )
              })}
            </div>
          ) : <p className="text-sm text-gray-400">加载中...</p>}
        </div>

        {/* API 延迟 */}
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="font-semibold mb-4">⚡ API 延迟统计</h2>
          {latency?.endpoints && Object.keys(latency.endpoints).length > 0 ? (
            <div className="space-y-2 max-h-[300px] overflow-y-auto">
              {Object.entries(latency.endpoints).map(([ep, data]: [string, any]) => (
                <div key={ep} className="flex items-center justify-between text-xs border-b border-gray-100 pb-2">
                  <span className="font-mono truncate max-w-[200px]">{ep}</span>
                  <div className="flex items-center gap-3 text-gray-500">
                    <span>avg: <span className="text-gray-700">{data.avg}ms</span></span>
                    <span>p95: <span className="text-yellow-600">{data.p95}ms</span></span>
                    <span className="text-gray-400">{data.count}次</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-400">暂无 API 调用记录</p>
          )}
        </div>

        {/* 备份管理 */}
        <div className="lg:col-span-2 bg-white border border-gray-200 rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold">💾 备份管理</h2>
            <button onClick={handleBackup} disabled={backingUp}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2">
              {backingUp ? '备份中...' : '创建备份'}
            </button>
          </div>
          {backups.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-8">暂无备份记录</p>
          ) : (
            <div className="divide-y">
              {backups.map((b: any) => (
                <div key={b.backup_id} className="py-3 flex items-center justify-between text-sm">
                  <div className="flex items-center gap-4">
                    <span className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center text-xs font-medium">B</span>
                    <div>
                      <span className="font-medium">{b.filename}</span>
                      <div className="flex gap-3 text-xs text-gray-400 mt-0.5">
                        <span>{b.created_at?.slice(0, 19) || '-'}</span>
                        <span>{(b.size_bytes / 1024).toFixed(1)} KB</span>
                        {b.tables && <span>{Object.keys(b.tables).length} 表</span>}
                      </div>
                    </div>
                  </div>
                  <button onClick={() => handleDeleteBackup(b.backup_id)} className="px-3 py-1 text-red-400 hover:text-red-600 text-xs">删除</button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default SystemMonitorPage
