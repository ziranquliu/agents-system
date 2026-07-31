import React, { useEffect, useState } from 'react'
import { triggerScan, getLatestScan, getScanResults, getScanHistory, cleanupOldScans, getScanAlerts, updateScanAlert, ScanSession, ScanItem, ScanAlert } from '../api/scanner'
import { useToast } from '../components/ui'

const ScannerDashboard: React.FC = () => {
  const toast = useToast()
  const [scan, setScan] = useState<ScanSession | null>(null)
  const [items, setItems] = useState<ScanItem[]>([])
  const [history, setHistory] = useState<ScanSession[]>([])
  const [alerts, setAlerts] = useState<ScanAlert[]>([])
  const [loading, setLoading] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [filterType, setFilterType] = useState<string>('')
  const [filterStatus, setFilterStatus] = useState<string>('')
  const [scanId, setScanId] = useState<string | null>(null)

  const loadData = async () => {
    setLoading(true)
    try {
      const latest = await getLatestScan()
      setScan(latest.scan)
      if (latest.scan) {
        setScanId(latest.scan.id)
        const results = await getScanResults(latest.scan.id)
        setItems(results.items)
      }
      const hist = await getScanHistory(1, 10)
      setHistory(hist.scans)
      const alertResp = await getScanAlerts({ page_size: 20 })
      setAlerts(alertResp.items)
    } catch {
      toast.error('加载扫描数据失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadData() }, [])

  const handleTriggerScan = async () => {
    setScanning(true)
    try {
      const resp = await triggerScan()
      toast.success(resp.message || '扫描已触发')
      // 延迟刷新以等待扫描完成
      setTimeout(loadData, 2000)
    } catch {
      toast.error('触发扫描失败')
    } finally {
      setScanning(false)
    }
  }

  const handleViewScan = async (id: string) => {
    setScanId(id)
    setLoading(true)
    try {
      const results = await getScanResults(id, filterType || undefined, filterStatus || undefined)
      setItems(results.items)
      // Also update current scan info from history
      const found = history.find(h => h.id === id)
      if (found) setScan(found)
    } catch {
      toast.error('加载扫描结果失败')
    } finally {
      setLoading(false)
    }
  }

  const handleFilter = async () => {
    if (!scanId) return
    setLoading(true)
    try {
      const results = await getScanResults(scanId, filterType || undefined, filterStatus || undefined)
      setItems(results.items)
    } catch {
      toast.error('筛选失败')
    } finally {
      setLoading(false)
    }
  }

  const handleCleanup = async () => {
    try {
      const resp = await cleanupOldScans(30)
      toast.success(`已清理 ${resp.deleted} 条旧记录`)
      loadData()
    } catch {
      toast.error('清理失败')
    }
  }

  const handleAlertStatus = async (alertId: string, status: string) => {
    try {
      await updateScanAlert(alertId, status)
      const alertResp = await getScanAlerts({ page_size: 20 })
      setAlerts(alertResp.items)
      toast.success('告警状态已更新')
    } catch {
      toast.error('更新告警状态失败')
    }
  }

  const summary = scan?.summary

  const statusColors: Record<string, string> = {
    healthy: 'bg-green-100 text-green-700 border-green-200',
    warning: 'bg-yellow-100 text-yellow-700 border-yellow-200',
    error: 'bg-red-100 text-red-700 border-red-200',
    unknown: 'bg-gray-100 text-gray-600 border-gray-200',
  }

  const typeColors: Record<string, string> = {
    agent: 'text-blue-600 bg-blue-50',
    skill: 'text-purple-600 bg-purple-50',
    mcp: 'text-teal-600 bg-teal-50',
  }

  const typeLabels: Record<string, string> = {
    agent: 'Agent',
    skill: 'Skill',
    mcp: 'MCP Server',
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">🔍 本地组件扫描器</h1>
          <p className="text-gray-500 mt-1">检测 Agent、Skill 和 MCP Server 的健康状态</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleCleanup}
            className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 text-sm"
          >
            清理历史
          </button>
          <button
            onClick={handleTriggerScan}
            disabled={scanning}
            className="px-5 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm flex items-center gap-2"
          >
            {scanning && <div className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" />}
            {scanning ? '扫描中...' : '立即扫描'}
          </button>
        </div>
      </div>

      {/* 状态卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white border border-gray-200 rounded-xl p-5 text-center">
          <div className="text-3xl font-bold text-gray-800">{summary?.checked ?? '-'}</div>
          <div className="text-sm text-gray-500 mt-1">总计检查</div>
        </div>
        <div className="bg-white border border-green-200 rounded-xl p-5 text-center">
          <div className="text-3xl font-bold text-green-600">{summary?.healthy ?? '-'}</div>
          <div className="text-sm text-green-500 mt-1">健康</div>
        </div>
        <div className="bg-white border border-yellow-200 rounded-xl p-5 text-center">
          <div className="text-3xl font-bold text-yellow-600">{summary?.warning ?? '-'}</div>
          <div className="text-sm text-yellow-500 mt-1">警告</div>
        </div>
        <div className="bg-white border border-red-200 rounded-xl p-5 text-center">
          <div className="text-3xl font-bold text-red-600">{summary?.error ?? '-'}</div>
          <div className="text-sm text-red-500 mt-1">异常</div>
        </div>
      </div>

      {/* 扫描信息 */}
      {scan && (
        <div className="bg-white border border-gray-200 rounded-xl p-4 mb-6 flex items-center justify-between text-sm">
          <div className="flex items-center gap-4">
            <span className="text-gray-400">扫描 ID: <span className="font-mono text-gray-600">{scan.id?.slice(0, 8)}...</span></span>
            <span className="text-gray-400">状态: <span className={`font-medium ${scan.status === 'completed' ? 'text-green-600' : 'text-yellow-600'}`}>{scan.status === 'completed' ? '✅ 已完成' : '⏳ 运行中'}</span></span>
            <span className="text-gray-400">时间: <span className="text-gray-600">{scan.completed_at ? new Date(scan.completed_at).toLocaleString() : '-'}</span></span>
          </div>
          <span className="text-xs text-gray-400">触发: {scan.triggered_by || 'system'}</span>
        </div>
      )}

      {/* 筛选 */}
      <div className="flex gap-3 mb-4">
        <select
          value={filterType}
          onChange={e => setFilterType(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">全部类型</option>
          <option value="agent">Agent</option>
          <option value="skill">Skill</option>
          <option value="mcp">MCP Server</option>
        </select>
        <select
          value={filterStatus}
          onChange={e => setFilterStatus(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">全部状态</option>
          <option value="healthy">健康</option>
          <option value="warning">警告</option>
          <option value="error">异常</option>
        </select>
        <button onClick={handleFilter} className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 text-sm">筛选</button>
      </div>

      {/* 结果列表 */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-5 py-3 border-b bg-gray-50 flex items-center justify-between">
          <h3 className="font-semibold text-sm">扫描结果</h3>
          <span className="text-xs text-gray-400">{items.length} 项</span>
        </div>
        {loading ? (
          <div className="flex justify-center py-12">
            <div className="animate-spin w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full" />
          </div>
        ) : items.length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            <div className="text-4xl mb-2">📋</div>
            <p className="text-sm">暂无扫描结果</p>
          </div>
        ) : (
          <div className="divide-y">
            {items.map(item => (
              <div key={item.id} className="px-5 py-4 hover:bg-gray-50">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusColors[item.status] || statusColors.unknown}`}>
                      {item.status === 'healthy' ? '健康' : item.status === 'warning' ? '警告' : item.status === 'error' ? '异常' : '未知'}
                    </span>
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${typeColors[item.component_type] || 'text-gray-600 bg-gray-50'}`}>
                      {typeLabels[item.component_type] || item.component_type}
                    </span>
                    <span className="font-medium text-sm">{item.component_name || item.component_id}</span>
                  </div>
                  <div className="text-xs text-gray-400">
                    {item.details && (
                      <span className="mr-3">
                        {item.component_type === 'agent' && `模型: ${item.details.model_provider || '-'}/${item.details.model_name || '-'}`}
                        {item.component_type === 'skill' && `绑定: ${item.details.bindings_count || 0} 次`}
                        {item.component_type === 'mcp' && `协议: ${item.details.protocol || '-'}`}
                      </span>
                    )}
                  </div>
                </div>
                {item.error_message && (
                  <p className="mt-1 text-xs text-red-500 ml-20">{item.error_message}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 历史记录 */}
      <div className="mt-6">
        <h3 className="font-semibold text-sm mb-3 text-gray-700">📜 扫描历史</h3>
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          {history.length === 0 ? (
            <div className="text-center py-6 text-gray-400 text-sm">暂无扫描历史</div>
          ) : (
            <div className="divide-y">
              {history.map(h => (
                <div
                  key={h.id}
                  className={`px-5 py-3 flex items-center justify-between hover:bg-gray-50 cursor-pointer text-sm ${scanId === h.id ? 'bg-blue-50' : ''}`}
                  onClick={() => handleViewScan(h.id)}
                >
                  <div className="flex items-center gap-3">
                    <span className={`w-2 h-2 rounded-full ${h.status === 'completed' ? 'bg-green-500' : 'bg-yellow-500'}`} />
                    <span className="text-gray-600">
                      {h.started_at ? new Date(h.started_at).toLocaleString() : '-'}
                    </span>
                    {h.summary && (
                      <span className="text-xs text-gray-400">
                        {h.summary.healthy}✓ {h.summary.warning}⚠ {h.summary.error}✗
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-gray-400">{h.triggered_by || 'system'}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 变化告警 */}
      <div className="mt-6">
        <h3 className="font-semibold text-sm mb-3 text-gray-700">🚨 扫描变化告警（状态降级/异常/恢复）</h3>
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          {alerts.length === 0 ? (
            <div className="text-center py-6 text-gray-400 text-sm">暂无告警</div>
          ) : (
            <div className="divide-y">
              {alerts.map(a => (
                <div key={a.id} className="px-5 py-3 flex items-center justify-between text-sm">
                  <div className="flex items-center gap-3">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                      a.severity === 'critical' ? 'bg-red-100 text-red-700' :
                      a.severity === 'warning' ? 'bg-yellow-100 text-yellow-700' : 'bg-green-100 text-green-700'
                    }`}>
                      {a.severity === 'critical' ? '严重' : a.severity === 'warning' ? '警告' : '恢复'}
                    </span>
                    <span className="text-gray-600">{a.message}</span>
                    <span className="text-xs text-gray-400">{a.component_name || a.component_id}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-gray-400">{a.created_at ? new Date(a.created_at).toLocaleString() : '-'}</span>
                    <select
                      value={a.status}
                      onChange={e => handleAlertStatus(a.id, e.target.value)}
                      className="text-xs border border-gray-300 rounded px-2 py-1"
                    >
                      <option value="open">未处理</option>
                      <option value="acknowledged">已确认</option>
                      <option value="resolved">已解决</option>
                    </select>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default ScannerDashboard
