import React, { useEffect, useState, useCallback } from 'react'
import {
  getLatestMetrics, getMetricHistory, getAgentRanking,
  listAlertConfigs, deleteAlertConfig,
  listAlerts, acknowledgeAlert, resolveAlert,
  listPanels, deletePanel, createPanel,
  AgentMetrics, AlertRecord, DashboardPanel,
} from '../api/monitoring'
import { useToast } from '../components/ui'

const SVGLineChart: React.FC<{ data: Array<{ time: string; value: number }>; width?: number; height?: number; color?: string }> = ({
  data, width = 300, height = 100, color = '#3b82f6',
}) => {
  if (!data || data.length < 2) return <div className="text-center py-4 text-xs text-gray-400">暂无数据</div>
  const values = data.map(d => d.value)
  const max = Math.max(...values, 1)
  const min = Math.min(...values, 0)
  const range = max - min || 1
  const padding = 5
  const w = width - padding * 2
  const h = height - padding * 2
  const stepX = w / (data.length - 1)
  const points = values.map((v, i) => `${(padding + i * stepX).toFixed(1)},${(padding + h - (v - min) / range * h).toFixed(1)}`).join(' ')
  return (
    <svg width={width} height={height} className="w-full">
      <polyline fill="none" stroke={color} strokeWidth="1.5" points={points} />
      <line x1={padding} y1={padding + h} x2={padding + w} y2={padding + h} stroke="#e5e7eb" strokeWidth="0.5" />
    </svg>
  )
}

const GaugeChart: React.FC<{ value: number; max?: number; label?: string; color?: string }> = ({
  value, max = 100, label, color,
}) => {
  const pct = Math.min(100, Math.max(0, (value / max) * 100))
  const strokeColor = color || (pct > 80 ? '#10b981' : pct > 60 ? '#3b82f6' : pct > 40 ? '#f59e0b' : '#ef4444')
  const r = 36
  const circ = 2 * Math.PI * r
  const dash = circ * pct / 100
  return (
    <div className="flex flex-col items-center">
      <svg width="90" height="90" viewBox="0 0 90 90">
        <circle cx="45" cy="45" r={r} fill="none" stroke="#e5e7eb" strokeWidth="8" />
        <circle cx="45" cy="45" r={r} fill="none" stroke={strokeColor} strokeWidth="8"
          strokeDasharray={`${dash} ${circ - dash}`} transform="rotate(-90 45 45)" strokeLinecap="round" />
        <text x="45" y="48" textAnchor="middle" fontSize="16" fontWeight="bold" fill={strokeColor}>{pct.toFixed(0)}</text>
      </svg>
      {label && <div className="text-xs text-gray-500 mt-0.5">{label}</div>}
    </div>
  )
}

const MonitoringDashboardPage: React.FC = () => {
  const toast = useToast()

  // 标签
  const [tab, setTab] = useState<'overview' | 'alerts' | 'panels'>('overview')

  // Overview
  const [metrics, setMetrics] = useState<AgentMetrics>({})
  const [ranking, setRanking] = useState<Array<Record<string, unknown>>>([])
  const [selectedAgent, setSelectedAgent] = useState<string>('')
  const [history, setHistory] = useState<Record<string, Array<{ time: string; value: number }>>>({})
  const [loading, setLoading] = useState(false)

  // Alerts
  const [alerts, setAlerts] = useState<AlertRecord[]>([])
  const [totalAlerts, setTotalAlerts] = useState(0)
  const [alertConfigs, setAlertConfigs] = useState<any[]>([])
  const [loadingAlerts, setLoadingAlerts] = useState(false)

  // Panels
  const [panels, setPanels] = useState<DashboardPanel[]>([])
  const [loadingPanels, setLoadingPanels] = useState(false)
  const [showCreatePanel, setShowCreatePanel] = useState(false)
  const [panelForm, setPanelForm] = useState({ title: '', chart_type: 'line', metric_names: 'health_score,qps', agent_ids: '', width: 2, height: 2 })

  const refreshMetrics = useCallback(async () => {
    setLoading(true)
    try {
      const [m, r] = await Promise.all([
        getLatestMetrics(),
        getAgentRanking('health_score', 10),
      ])
      setMetrics(m)
      setRanking(r)
      const agents = Object.keys(m)
      if (agents.length > 0 && !selectedAgent) {
        setSelectedAgent(agents[0])
      }
    } catch { toast.error('加载指标失败') }
    finally { setLoading(false) }
  }, [toast, selectedAgent])

  useEffect(() => { if (tab === 'overview') refreshMetrics() }, [tab])

  const loadHistory = async (agentId: string) => {
    setSelectedAgent(agentId)
    try {
      const h = await getMetricHistory(agentId, 'health_score,qps,success_rate,latency_p95', 24, 10)
      setHistory(h)
    } catch { toast.error('加载历史失败') }
  }

  useEffect(() => {
    if (selectedAgent && tab === 'overview') loadHistory(selectedAgent)
  }, [selectedAgent])

  const loadAlerts = useCallback(async () => {
    setLoadingAlerts(true)
    try {
      const [a, c] = await Promise.all([
        listAlerts({ offset: 0, limit: 50 }),
        listAlertConfigs(),
      ])
      setAlerts(a.data || [])
      setTotalAlerts(a.total || 0)
      setAlertConfigs(c || [])
    } catch { toast.error('加载告警失败') }
    finally { setLoadingAlerts(false) }
  }, [toast])

  useEffect(() => { if (tab === 'alerts') loadAlerts() }, [tab])

  const loadPanels = useCallback(async () => {
    setLoadingPanels(true)
    try {
      const p = await listPanels()
      setPanels(p || [])
    } catch { toast.error('加载面板失败') }
    finally { setLoadingPanels(false) }
  }, [toast])

  useEffect(() => { if (tab === 'panels') loadPanels() }, [tab])

  const handleResolveAlert = async (id: string) => {
    try { await resolveAlert(id); toast.success('告警已解决'); loadAlerts() }
    catch { toast.error('操作失败') }
  }

  const handleCreatePanel = async () => {
    if (!panelForm.title.trim()) { toast.error('请输入面板标题'); return }
    try {
      await createPanel({
        title: panelForm.title,
        chart_type: panelForm.chart_type,
        metric_names: panelForm.metric_names.split(',').map(s => s.trim()).filter(Boolean),
        agent_ids: panelForm.agent_ids ? panelForm.agent_ids.split(',').map(s => s.trim()).filter(Boolean) : [],
        width: panelForm.width,
        height: panelForm.height,
      })
      toast.success('面板已创建')
      setShowCreatePanel(false)
      setPanelForm({ title: '', chart_type: 'line', metric_names: 'health_score,qps', agent_ids: '', width: 2, height: 2 })
      loadPanels()
    } catch { toast.error('创建失败') }
  }

  const handleDeletePanel = async (id: string) => {
    if (!confirm('删除面板？')) return
    try { await deletePanel(id); toast.success('已删除'); loadPanels() }
    catch { toast.error('删除失败') }
  }

  const agentList = Object.values(metrics)

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold flex items-center gap-2">📊 多智能体监控看板</h1>
        <p className="text-gray-500 mt-1">健康评分 · 实时曲线 · 告警管理 · 自定义面板</p>
      </div>

      <div className="flex gap-1 mb-6 border-b">
        {[
          { key: 'overview', label: '📊 概览' },
          { key: 'alerts', label: `🔔 告警 (${alerts.filter(a => a.status === 'firing').length})` },
          { key: 'panels', label: '📋 面板' },
        ].map(t => (
          <button key={t.key} onClick={() => setTab(t.key as any)}
            className={`px-4 py-2 text-sm border-b-2 ${tab === t.key ? 'border-blue-500 text-blue-600 font-medium' : 'border-transparent text-gray-500'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* ==================== Overview ==================== */}
      {tab === 'overview' && (
        <div className="space-y-4">
          <button onClick={refreshMetrics} disabled={loading}
            className="px-4 py-1.5 bg-blue-600 text-white rounded-lg text-sm disabled:opacity-50">
            {loading ? '刷新中...' : '🔄 刷新'}
          </button>

          {/* Agent 卡片 */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            {agentList.map(a => (
              <div key={a.agent_id} onClick={() => loadHistory(a.agent_id)}
                className={`bg-white border-2 rounded-xl p-4 cursor-pointer transition-all hover:shadow-md
                  ${selectedAgent === a.agent_id ? 'border-blue-400 shadow' : 'border-gray-200'}`}>
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-sm truncate">{a.agent_name}</div>
                    <div className="text-xs text-gray-400 font-mono truncate">{a.agent_id.slice(0, 16)}</div>
                  </div>
                  <GaugeChart value={a.health_score} label="健康" />
                </div>
                <div className="grid grid-cols-2 gap-x-3 gap-y-1 mt-2 text-xs">
                  <span className="text-gray-500">QPS <strong className="text-gray-700">{a.qps?.toFixed(1)}</strong></span>
                  <span className="text-gray-500">成功率 <strong className={a.success_rate >= 99 ? 'text-green-600' : 'text-red-600'}>{a.success_rate?.toFixed(1)}%</strong></span>
                  <span className="text-gray-500">P50 <strong className="text-gray-700">{a.latency_p50?.toFixed(0)}ms</strong></span>
                  <span className="text-gray-500">P95 <strong className={a.latency_p95 < 1000 ? 'text-green-600' : 'text-red-600'}>{a.latency_p95?.toFixed(0)}ms</strong></span>
                  <span className="text-gray-500">内存 <strong className="text-gray-700">{a.memory_mb?.toFixed(0)}MB</strong></span>
                  <span className="text-gray-500">CPU <strong className={a.cpu_percent < 80 ? 'text-green-600' : 'text-red-600'}>{a.cpu_percent?.toFixed(1)}%</strong></span>
                </div>
              </div>
            ))}
            {agentList.length === 0 && !loading && (
              <div className="col-span-full text-center py-12 text-gray-400 text-sm">
                暂无指标数据 — 通过 API 记录指标后即可查看
              </div>
            )}
          </div>

          {/* 历史曲线 */}
          {selectedAgent && Object.keys(history).length > 0 && (
            <div className="bg-white border border-gray-200 rounded-xl p-5">
              <h3 className="font-semibold text-sm mb-3">{selectedAgent.slice(0, 16)} 历史曲线 (24h)</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {Object.entries(history).map(([name, points]) => (
                  <div key={name} className="bg-gray-50 rounded-lg p-3">
                    <div className="text-xs font-medium text-gray-500 mb-1">{name}</div>
                    <SVGLineChart data={points} width={350} height={80}
                      color={name === 'health_score' ? '#10b981' : name === 'success_rate' ? '#3b82f6' : name === 'qps' ? '#8b5cf6' : '#f59e0b'} />
                    {points.length > 0 && (
                      <div className="flex justify-between text-xs text-gray-400 mt-1">
                        <span>min: {Math.min(...points.map(p => p.value)).toFixed(1)}</span>
                        <span>avg: {(points.reduce((s, p) => s + p.value, 0) / points.length).toFixed(1)}</span>
                        <span>max: {Math.max(...points.map(p => p.value)).toFixed(1)}</span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 排行 */}
          {ranking.length > 0 && (
            <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
              <div className="px-5 py-3 border-b bg-gray-50 text-sm font-semibold">🏆 Agent 健康排行</div>
              <div className="divide-y">
                {ranking.map((r: any, i: number) => (
                  <div key={r.agent_id} className="px-5 py-2.5 flex items-center justify-between text-sm">
                    <div className="flex items-center gap-3">
                      <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold text-white
                        ${i === 0 ? 'bg-yellow-400' : i < 3 ? 'bg-gray-400' : 'bg-gray-200 text-gray-500'}`}>{i + 1}</span>
                      <span className="font-medium">{r.agent_name || r.agent_id?.slice(0, 12)}</span>
                    </div>
                    <div className="flex gap-4 text-xs">
                      <span>健康: <strong className="text-green-600">{r.health_score?.toFixed(1)}</strong></span>
                      <span>QPS: {r.qps?.toFixed(1)}</span>
                      <span>P95: {r.latency_p95?.toFixed(0)}ms</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ==================== Alerts ==================== */}
      {tab === 'alerts' && (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <button onClick={loadAlerts} className="px-4 py-1.5 bg-blue-600 text-white rounded-lg text-sm">刷新</button>
            <span className="text-sm text-gray-500">
              {alerts.filter(a => a.status === 'firing').length} 个活跃告警 · {alerts.filter(a => a.status === 'acknowledged').length} 个已确认
            </span>
          </div>

          {/* 告警配置 */}
          <details className="bg-white border border-gray-200 rounded-xl">
            <summary className="px-5 py-3 font-semibold text-sm cursor-pointer hover:bg-gray-50">⚙️ 告警配置 ({alertConfigs.length})</summary>
            {alertConfigs.length > 0 ? (
              <div className="divide-y border-t">
                {alertConfigs.map((c: any) => (
                  <div key={c.id} className="px-5 py-3 flex items-center justify-between text-sm">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className={`px-1.5 py-0.5 rounded text-xs font-bold ${c.priority === 'P0' ? 'bg-red-100 text-red-700' : c.priority === 'P1' ? 'bg-orange-100 text-orange-700' : c.priority === 'P2' ? 'bg-yellow-100 text-yellow-700' : 'bg-blue-100 text-blue-700'}`}>{c.priority}</span>
                        <span className="font-medium">{c.name}</span>
                        {!c.enabled && <span className="text-xs text-gray-400">(已禁用)</span>}
                      </div>
                      <div className="text-xs text-gray-500 mt-0.5">{c.metric_name} {c.operator} {c.threshold} / 持续 {c.duration_seconds}s</div>
                    </div>
                    <button onClick={() => deleteAlertConfig(c.id).then(() => { toast.success('已删除'); loadAlerts() })}
                      className="px-2 py-1 text-xs text-red-500 hover:bg-red-50 rounded">删除</button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="px-5 py-4 text-sm text-gray-400">暂无告警配置</div>
            )}
          </details>

          {/* 告警记录 */}
          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
            <div className="px-5 py-3 border-b bg-gray-50 text-sm font-semibold">告警记录 ({totalAlerts})</div>
            {loadingAlerts ? (
              <div className="flex justify-center py-12"><div className="animate-spin w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full" /></div>
            ) : alerts.length === 0 ? (
              <div className="text-center py-12 text-gray-400 text-sm">无告警 🎉</div>
            ) : (
              <div className="divide-y">
                {alerts.map(a => (
                  <div key={a.id} className="px-5 py-3 text-sm">
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className={`px-1.5 py-0.5 rounded text-xs font-bold ${a.priority === 'P0' ? 'bg-red-100 text-red-700' : a.priority === 'P1' ? 'bg-orange-100 text-orange-700' : a.priority === 'P2' ? 'bg-yellow-100 text-yellow-700' : 'bg-blue-100 text-blue-700'}`}>{a.priority}</span>
                          <span className={`px-2 py-0.5 rounded text-xs ${a.status === 'firing' ? 'bg-red-100 text-red-700' : a.status === 'acknowledged' ? 'bg-yellow-100 text-yellow-700' : 'bg-green-100 text-green-700'}`}>{a.status}</span>
                          <span className="font-medium">{a.alert_name}</span>
                        </div>
                        <div className="text-xs text-gray-500 mt-0.5">
                          Agent: {a.agent_id.slice(0, 16)}... | {a.metric_name} = {a.current_value} ({a.operator} {a.threshold})
                        </div>
                        <div className="text-xs text-gray-400 mt-0.5">
                          {a.fired_at ? new Date(a.fired_at).toLocaleString() : ''}
                        </div>
                      </div>
                      <div className="flex gap-1">
                        {a.status === 'firing' && (
                          <button onClick={() => acknowledgeAlert(a.id).then(loadAlerts)}
                            className="px-2 py-1 text-xs bg-yellow-100 text-yellow-700 rounded">确认</button>
                        )}
                        {['firing', 'acknowledged'].includes(a.status) && (
                          <button onClick={() => handleResolveAlert(a.id)}
                            className="px-2 py-1 text-xs bg-green-100 text-green-700 rounded">解决</button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ==================== Panels ==================== */}
      {tab === 'panels' && (
        <div className="space-y-4">
          <div className="flex gap-2">
            <button onClick={() => setShowCreatePanel(true)} className="px-4 py-1.5 bg-blue-600 text-white rounded-lg text-sm">+ 新建面板</button>
            <button onClick={loadPanels} className="px-4 py-1.5 border rounded-lg text-sm">刷新</button>
          </div>

          {loadingPanels ? (
            <div className="flex justify-center py-12"><div className="animate-spin w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full" /></div>
          ) : panels.length === 0 ? (
            <div className="bg-white border border-gray-200 rounded-xl text-center py-12 text-gray-400 text-sm">
              暂无自定义面板 — 点击上方按钮创建
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {panels.map(p => (
                <div key={p.id} className="bg-white border border-gray-200 rounded-xl p-4">
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <h3 className="font-semibold text-sm">{p.title}</h3>
                      <div className="text-xs text-gray-400">
                        {p.chart_type} · {p.metric_names.join(', ')}
                        {p.agent_ids.length > 0 && ` · ${p.agent_ids.length} agents`}
                      </div>
                    </div>
                    <button onClick={() => handleDeletePanel(p.id)}
                      className="text-xs text-red-400 hover:text-red-600">删除</button>
                  </div>
                  <div className="bg-gray-50 rounded-lg h-24 flex items-center justify-center text-xs text-gray-400">
                    {p.chart_type === 'line' ? '📈 Line Chart' : p.chart_type === 'bar' ? '📊 Bar Chart' : p.chart_type === 'number' ? '🔢 Number' : '📋 Panel'}
                  </div>
                  <div className="mt-2 text-xs text-gray-400 flex gap-2">
                    <span>位置: ({p.position_x}, {p.position_y})</span>
                    <span>尺寸: {p.width}×{p.height}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 创建面板弹窗 */}
      {showCreatePanel && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setShowCreatePanel(false)}>
          <div className="bg-white rounded-2xl w-full max-w-md m-4 p-6" onClick={e => e.stopPropagation()}>
            <h2 className="text-lg font-bold mb-4">新建面板</h2>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium mb-1">标题 *</label>
                <input value={panelForm.title} onChange={e => setPanelForm(f => ({ ...f, title: e.target.value }))}
                  className="w-full px-3 py-2 border rounded-lg text-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">图表类型</label>
                <select value={panelForm.chart_type} onChange={e => setPanelForm(f => ({ ...f, chart_type: e.target.value }))}
                  className="w-full px-3 py-2 border rounded-lg text-sm">
                  <option value="line">折线图</option>
                  <option value="bar">柱状图</option>
                  <option value="number">数字</option>
                  <option value="table">表格</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">指标 (逗号分隔)</label>
                <input value={panelForm.metric_names} onChange={e => setPanelForm(f => ({ ...f, metric_names: e.target.value }))}
                  placeholder="health_score, qps, latency_p95" className="w-full px-3 py-2 border rounded-lg text-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Agent IDs (逗号分隔，留空为全部)</label>
                <input value={panelForm.agent_ids} onChange={e => setPanelForm(f => ({ ...f, agent_ids: e.target.value }))}
                  className="w-full px-3 py-2 border rounded-lg text-sm" />
              </div>
            </div>
            <div className="flex gap-3 justify-end mt-6">
              <button onClick={() => setShowCreatePanel(false)} className="px-4 py-2 border rounded-lg text-sm">取消</button>
              <button onClick={handleCreatePanel} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm">创建</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default MonitoringDashboardPage
