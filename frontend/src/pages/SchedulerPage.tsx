import { useState, useEffect, useCallback } from 'react'
import { getSchedulerStatus, startScheduler, stopScheduler, triggerSchedulerTask } from '../api/scheduler'

interface Job { id: string; name: string; next_run: string | null }

const TASK_META: Record<string, { label: string; desc: string }> = {
  scan: { label: '组件扫描', desc: '4.10 本地组件扫描（Agent/Skill/MCP）' },
  update_check: { label: '更新检测', desc: '4.11 统一更新检测' },
  maintenance: { label: '定期维护', desc: '4.22.4 缓存/会话/日志清理' },
  backup: { label: '全量备份', desc: '4.23 每日全量备份' },
  backup_incremental: { label: '增量备份', desc: '4.23 每 6 小时增量备份' },
  drill: { label: '恢复演练', desc: '4.23 每周恢复演练' },
  audit: { label: '审计归档', desc: '4.25 归档 + 保留期清理' },
  health: { label: '健康快照', desc: '4.24 定时健康检查快照' },
}

export default function SchedulerPage() {
  const [status, setStatus] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [triggering, setTriggering] = useState('')

  const fetchStatus = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const res = await getSchedulerStatus()
      setStatus(res.data)
    } catch (e: any) {
      setError(e?.response?.data?.detail || '加载调度器状态失败')
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { fetchStatus() }, [fetchStatus])

  const doStart = async () => {
    setLoading(true); setError(''); setSuccess('')
    try {
      await startScheduler()
      setSuccess('调度器已启动')
      fetchStatus()
    } catch (e: any) { setError(e?.response?.data?.detail || '启动失败') } finally { setLoading(false) }
  }

  const doStop = async () => {
    if (!window.confirm('确定停止全局调度器？定时扫描/备份/维护将暂停。')) return
    setLoading(true); setError(''); setSuccess('')
    try {
      await stopScheduler()
      setSuccess('调度器已停止')
      fetchStatus()
    } catch (e: any) { setError(e?.response?.data?.detail || '停止失败') } finally { setLoading(false) }
  }

  const doTrigger = async (task: string) => {
    setTriggering(task); setError(''); setSuccess('')
    try {
      await triggerSchedulerTask(task)
      setSuccess(`任务「${TASK_META[task]?.label || task}」执行完成`)
    } catch (e: any) {
      setError(e?.response?.data?.detail || `任务 ${task} 执行失败`)
    } finally { setTriggering('') }
  }

  const btnCls = 'px-3 py-1.5 rounded text-sm bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50'
  const btnSec = 'px-3 py-1.5 rounded text-sm border border-gray-300 hover:bg-gray-50'

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">全局定时调度器</h1>
          <p className="text-sm text-gray-500 mt-1">APScheduler 集成 · 组件扫描 / 更新检测 / 定期维护 / 定时备份 / 审计归档</p>
        </div>
        <div className="flex gap-2">
          <button className={btnSec} onClick={fetchStatus} disabled={loading}>刷新</button>
          {status?.running ? (
            <button className="px-3 py-1.5 rounded text-sm bg-red-600 text-white hover:bg-red-700" onClick={doStop}>停止调度器</button>
          ) : (
            <button className={btnCls} onClick={doStart}>启动调度器</button>
          )}
        </div>
      </div>

      {error && <div className="bg-red-50 text-red-700 border border-red-200 rounded px-4 py-2 mb-4 text-sm">{error}</div>}
      {success && <div className="bg-green-50 text-green-700 border border-green-200 rounded px-4 py-2 mb-4 text-sm">{success}</div>}

      {status && (
        <div className={`inline-flex items-center gap-2 px-4 py-2 rounded mb-4 text-sm font-medium ${status.running ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-gray-100 text-gray-600 border border-gray-200'}`}>
          <span className={`w-2.5 h-2.5 rounded-full ${status.running ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`} />
          {status.running ? `运行中 · ${status.jobs.length} 个定时任务` : '已停止'}
        </div>
      )}

      {/* 定时任务列表 */}
      <div className="bg-white border rounded overflow-hidden mb-6">
        <div className="px-4 py-3 border-b bg-gray-50 font-semibold text-gray-700">定时任务（8 项）</div>
        <table className="w-full text-sm">
          <thead className="text-gray-500 text-left text-xs">
            <tr>
              <th className="px-4 py-2">任务 ID</th>
              <th className="px-4 py-2">功能</th>
              <th className="px-4 py-2">下次执行</th>
              <th className="px-4 py-2">手动触发</th>
            </tr>
          </thead>
          <tbody>
            {status?.jobs?.map((job: Job) => {
              const idToKey: Record<string, string> = {
                scan_every_5min: 'scan', update_check_24h: 'update_check', maintenance_dynamic_1h: 'maintenance',
                backup_full_daily: 'backup', backup_incremental_6h: 'backup_incremental', backup_drill_weekly: 'drill',
                audit_maintenance_daily: 'audit', health_snapshot_15min: 'health',
              }
              const metaKey = idToKey[job.id]
              const meta = TASK_META[metaKey || '']
              return (
                <tr key={job.id} className="border-t hover:bg-gray-50">
                  <td className="px-4 py-2 font-mono text-xs">{job.id}</td>
                  <td className="px-4 py-2">
                    <div className="font-medium">{meta?.label || job.id}</div>
                    <div className="text-xs text-gray-400">{meta?.desc || ''}</div>
                  </td>
                  <td className="px-4 py-2 text-xs">{job.next_run ? job.next_run.replace('T', ' ').slice(0, 19) : '-'}</td>
                  <td className="px-4 py-2">
                    {metaKey && (
                      <button className="text-xs text-blue-600 hover:underline" disabled={!!triggering}
                        onClick={() => doTrigger(metaKey)}>
                        {triggering === metaKey ? '执行中…' : '立即执行'}
                      </button>
                    )}
                  </td>
                </tr>
              )
            })}
            {(!status?.jobs || status.jobs.length === 0) && (
              <tr><td colSpan={4} className="px-4 py-8 text-center text-gray-400">调度器未运行，无任务</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* 任务说明 */}
      <div className="bg-white border rounded p-4">
        <h3 className="font-semibold mb-2 text-gray-700">调度说明</h3>
        <div className="grid md:grid-cols-2 gap-3 text-sm text-gray-600">
          <div className="flex gap-2"><span className="text-blue-500">●</span>组件扫描每 5 分钟自动执行，发现 Agent 状态/Skill 依赖/MCP 连接变化</div>
          <div className="flex gap-2"><span className="text-blue-500">●</span>更新检测每 24 小时检查本地组件与市场版本差异</div>
          <div className="flex gap-2"><span className="text-blue-500">●</span>定期维护每小时执行一次（按维护任务 cron 配置动态调度）</div>
          <div className="flex gap-2"><span className="text-blue-500">●</span>每日 03:00 全量备份 · 每 6 小时增量备份 · 每周日 04:00 恢复演练</div>
          <div className="flex gap-2"><span className="text-blue-500">●</span>每日 02:30 审计归档 + 合规保留期清理</div>
          <div className="flex gap-2"><span className="text-blue-500">●</span>健康快照每 15 分钟对已配置健康检查的 Agent 执行 L1-L2 检查</div>
        </div>
      </div>
    </div>
  )
}
