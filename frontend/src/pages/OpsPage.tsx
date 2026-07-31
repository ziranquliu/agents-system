import { useState, useEffect, useCallback } from 'react'
import {
  listDeployments, createDeployment, updateDeploymentStatus, rollbackDeployment,
  deleteDeployment, getDeploymentStats,
  listScalingPolicies, upsertScalingPolicy, listScalingEvents, evaluateScaling, getScalingStats,
  searchLogs, getLogStats,
  listMaintenanceTasks, createMaintenanceTask, updateMaintenanceTask, deleteMaintenanceTask,
  executeMaintenanceTask, listMaintenanceExecutions,
  listHealRules, createHealRule, updateHealRule, listHealRecords, getHealStats,
  generateReport, listReports, deleteReport,
  getOpsDashboard,
} from '../api/ops'

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-gray-100 text-gray-700',
  deploying: 'bg-blue-100 text-blue-700',
  health_checking: 'bg-yellow-100 text-yellow-700',
  healthy: 'bg-green-100 text-green-700',
  degraded: 'bg-orange-100 text-orange-700',
  failed: 'bg-red-100 text-red-700',
  rolled_back: 'bg-purple-100 text-purple-700',
}

const TABS = [
  { key: 'overview', label: '运维概览' },
  { key: 'deploy', label: '自动部署' },
  { key: 'scaling', label: 'Auto Scaling' },
  { key: 'logs', label: '日志管理' },
  { key: 'maintenance', label: '定期维护' },
  { key: 'heal', label: '异常自愈' },
  { key: 'reports', label: '运维报告' },
]

interface Row { id: string; [key: string]: any }

export default function OpsPage() {
  const [activeTab, setActiveTab] = useState('overview')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // overview
  const [overview, setOverview] = useState<any>(null)

  // deploy
  const [deployments, setDeployments] = useState<Row[]>([])
  const [deployStats, setDeployStats] = useState<any>(null)
  const [showDeployForm, setShowDeployForm] = useState(false)
  const [deployForm, setDeployForm] = useState({ agent_name: '', template_yaml: 'name: my-agent\nversion: 1.0.0\n', version: '1.0.0' })

  // scaling
  const [policies, setPolicies] = useState<Row[]>([])
  const [scalingEvents, setScalingEvents] = useState<Row[]>([])
  const [scalingStats, setScalingStats] = useState<any>(null)
  const [showPolicyForm, setShowPolicyForm] = useState(false)
  const [policyForm, setPolicyForm] = useState<any>({ agent_id: '', agent_name: '', metric_type: 'cpu_usage', scale_out_threshold: 70, scale_in_threshold: 30, min_instances: 1, max_instances: 10 })

  // logs
  const [logs, setLogs] = useState<Row[]>([])
  const [logStats, setLogStats] = useState<any>(null)
  const [logQuery, setLogQuery] = useState({ keyword: '', level: '', agent_id: '' })

  // maintenance
  const [maintTasks, setMaintTasks] = useState<Row[]>([])
  const [maintExecs, setMaintExecs] = useState<Row[]>([])
  const [showMaintForm, setShowMaintForm] = useState(false)
  const [maintForm, setMaintForm] = useState({ task_type: 'session_cleanup', name: '', cron_expression: '0 2 * * *' })

  // heal
  const [healRules, setHealRules] = useState<Row[]>([])
  const [healRecords, setHealRecords] = useState<Row[]>([])
  const [healStats, setHealStats] = useState<any>(null)
  const [showHealForm, setShowHealForm] = useState(false)
  const [healForm, setHealForm] = useState({ agent_id: '', anomaly_type: 'error_rate', heal_level: 'restart', auto_heal: true })

  // reports
  const [reports, setReports] = useState<Row[]>([])

  const fetchOverview = useCallback(async () => {
    try { setOverview((await getOpsDashboard()).data) } catch (e: any) { setError(e?.message || '加载概览失败') }
  }, [])

  const fetchDeployments = useCallback(async () => {
    try {
      const [r1, r2] = await Promise.all([listDeployments({ limit: 50 }), getDeploymentStats()])
      setDeployments(r1.data?.items || [])
      setDeployStats(r2.data)
    } catch (e: any) { setError(e?.message || '加载部署失败') }
  }, [])

  const fetchScaling = useCallback(async () => {
    try {
      const [p, ev, st] = await Promise.all([listScalingPolicies({ limit: 50 }), listScalingEvents({ limit: 50, days: 7 }), getScalingStats(7)])
      setPolicies(p.data?.items || [])
      setScalingEvents(ev.data?.items || [])
      setScalingStats(st.data)
    } catch (e: any) { setError(e?.message || '加载扩缩容失败') }
  }, [])

  const fetchLogs = useCallback(async () => {
    try {
      const [l, st] = await Promise.all([searchLogs({ ...logQuery, limit: 100 }), getLogStats(1)])
      setLogs(l.data?.items || [])
      setLogStats(st.data)
    } catch (e: any) { setError(e?.message || '加载日志失败') }
  }, [logQuery])

  const fetchMaintenance = useCallback(async () => {
    try {
      const [t, ex] = await Promise.all([listMaintenanceTasks({ limit: 50 }), listMaintenanceExecutions({ limit: 50, days: 7 })])
      setMaintTasks(t.data?.items || [])
      setMaintExecs(ex.data?.items || [])
    } catch (e: any) { setError(e?.message || '加载维护任务失败') }
  }, [])

  const fetchHeal = useCallback(async () => {
    try {
      const [r, rec, st] = await Promise.all([listHealRules({ limit: 50 }), listHealRecords({ limit: 50, days: 30 }), getHealStats(30)])
      setHealRules(r.data?.items || [])
      setHealRecords(rec.data?.items || [])
      setHealStats(st.data)
    } catch (e: any) { setError(e?.message || '加载自愈数据失败') }
  }, [])

  const fetchReports = useCallback(async () => {
    try { setReports((await listReports({ limit: 50 })).data?.items || []) } catch (e: any) { setError(e?.message || '加载报告失败') }
  }, [])

  useEffect(() => {
    setLoading(true)
    Promise.all([fetchOverview(), fetchDeployments(), fetchScaling(), fetchLogs(), fetchMaintenance(), fetchHeal(), fetchReports()])
      .finally(() => setLoading(false))
  }, [fetchOverview, fetchDeployments, fetchScaling, fetchLogs, fetchMaintenance, fetchHeal, fetchReports])

  const handleCreateDeployment = async () => {
    try {
      await createDeployment(deployForm)
      setShowDeployForm(false)
      setDeployForm({ agent_name: '', template_yaml: 'name: my-agent\nversion: 1.0.0\n', version: '1.0.0' })
      fetchDeployments(); fetchOverview()
    } catch (e: any) { setError(e?.message || '创建部署失败') }
  }

  const handleRollback = async (id: string) => {
    try { await rollbackDeployment(id); fetchDeployments() } catch (e: any) { setError(e?.message) }
  }

  const handleCreatePolicy = async () => {
    try {
      await upsertScalingPolicy(policyForm)
      setShowPolicyForm(false)
      fetchScaling()
    } catch (e: any) { setError(e?.message || '创建策略失败') }
  }

  const handleEvaluate = async (p: any) => {
    try {
      const r = await evaluateScaling({ agent_id: p.agent_id, current_instances: 3, metric_type: p.metric_type, metric_value: 85 })
      alert(r.data?.message || '评估完成')
      fetchScaling()
    } catch (e: any) { setError(e?.message) }
  }

  const handleCreateMaint = async () => {
    try {
      await createMaintenanceTask(maintForm)
      setShowMaintForm(false)
      setMaintForm({ task_type: 'session_cleanup', name: '', cron_expression: '0 2 * * *' })
      fetchMaintenance()
    } catch (e: any) { setError(e?.message || '创建任务失败') }
  }

  const handleRunMaint = async (id: string) => {
    try {
      await executeMaintenanceTask(id, { status: 'success', items_processed: 100, items_cleaned: 50 })
      fetchMaintenance()
    } catch (e: any) { setError(e?.message) }
  }

  const handleCreateHeal = async () => {
    try {
      await createHealRule(healForm)
      setShowHealForm(false)
      setHealForm({ agent_id: '', anomaly_type: 'error_rate', heal_level: 'restart', auto_heal: true })
      fetchHeal()
    } catch (e: any) { setError(e?.message || '创建规则失败') }
  }

  const handleGenerateReport = async (type: string) => {
    try {
      await generateReport({ report_type: type })
      fetchReports()
    } catch (e: any) { setError(e?.message) }
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">智能体自动化运维</h1>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg">{error}</div>
      )}
      {loading && <div className="mb-4 text-sm text-gray-500">加载中...</div>}

      <div className="flex space-x-2 mb-6 overflow-x-auto pb-2">
        {TABS.map(t => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            className={`px-4 py-2 rounded-lg text-sm whitespace-nowrap transition-colors ${activeTab === t.key ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ===== 概览 ===== */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard title="部署成功率" value={overview?.deployment?.success_rate != null ? `${overview.deployment.success_rate}%` : '-'} desc={`成功 ${overview?.deployment?.successful ?? 0} / 总 ${overview?.deployment?.total ?? 0}`} />
            <StatCard title="7天扩缩容事件" value={overview?.scaling?.total ?? '-'} desc={`扩容 ${overview?.scaling?.scale_out ?? 0} / 缩容 ${overview?.scaling?.scale_in ?? 0}`} />
            <StatCard title="今日日志量" value={overview?.logs?.today_count ?? '-'} desc={`错误 ${overview?.logs?.error_count ?? 0} 条`} />
            <StatCard title="7天自愈事件" value={overview?.healing?.total ?? '-'} desc={`成功率 ${overview?.healing?.success_rate ?? '-'}%`} />
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <section className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <h3 className="font-semibold text-gray-800 mb-3">近期部署</h3>
              <MiniTable
                rows={deployments.slice(0, 5)}
                cols={[{ key: 'agent_name', label: 'Agent' }, { key: 'version', label: '版本' }, { key: 'status', label: '状态', render: v => <Badge text={v} map={STATUS_COLORS} /> }]}
              />
            </section>
            <section className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <h3 className="font-semibold text-gray-800 mb-3">近期自愈事件</h3>
              <MiniTable
                rows={healRecords.slice(0, 5)}
                cols={[{ key: 'agent_name', label: 'Agent' }, { key: 'anomaly_type', label: '异常类型' }, { key: 'status', label: '状态' }]}
              />
            </section>
          </div>
        </div>
      )}

      {/* ===== 自动部署 ===== */}
      {activeTab === 'deploy' && (
        <div className="space-y-6">
          <div className="flex justify-end">
            <button onClick={() => setShowDeployForm(!showDeployForm)} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">
              {showDeployForm ? '取消' : '+ 新建部署'}
            </button>
          </div>
          {showDeployForm && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 space-y-3">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-gray-600 mb-1">Agent 名称</label>
                  <input value={deployForm.agent_name} onChange={e => setDeployForm({ ...deployForm, agent_name: e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm" placeholder="agent-1" />
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">版本</label>
                  <input value={deployForm.version} onChange={e => setDeployForm({ ...deployForm, version: e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm" placeholder="1.0.0" />
                </div>
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">部署模板 (YAML)</label>
                <textarea value={deployForm.template_yaml} onChange={e => setDeployForm({ ...deployForm, template_yaml: e.target.value })}
                  rows={6} className="w-full p-2 border border-gray-200 rounded-lg text-sm font-mono" />
              </div>
              <button onClick={handleCreateDeployment} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">创建部署</button>
            </div>
          )}
          <section className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            <div className="flex justify-between items-center mb-3">
              <h3 className="font-semibold text-gray-800">部署记录</h3>
              {deployStats && (
                <span className="text-sm text-gray-500">成功率 <b className="text-green-600">{deployStats.success_rate}%</b> · 失败 {deployStats.failed}</span>
              )}
            </div>
            <DataTable
              rows={deployments}
              cols={[
                { key: 'agent_name', label: 'Agent' },
                { key: 'version', label: '版本' },
                { key: 'status', label: '状态', render: v => <Badge text={v} map={STATUS_COLORS} /> },
                { key: 'health_score', label: '健康分', render: v => (v != null ? `${v}` : '-') },
                { key: 'created_at', label: '创建时间', render: v => fmtTime(v) },
                { key: 'id', label: '操作', render: (_, row) => (
                  <div className="flex space-x-2">
                    <button onClick={() => updateDeploymentStatus(row.id, { status: 'healthy' })} className="text-xs text-blue-600 hover:underline">标记健康</button>
                    <button onClick={() => handleRollback(row.id)} className="text-xs text-orange-600 hover:underline">回滚</button>
                    <button onClick={() => deleteDeployment(row.id).then(fetchDeployments)} className="text-xs text-red-600 hover:underline">删除</button>
                  </div>
                ) },
              ]}
            />
          </section>
        </div>
      )}

      {/* ===== Auto Scaling ===== */}
      {activeTab === 'scaling' && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard title="策略数" value={policies.length} />
            <StatCard title="7天扩容" value={scalingStats?.scale_out ?? 0} />
            <StatCard title="7天缩容" value={scalingStats?.scale_in ?? 0} />
            <StatCard title="事件总数" value={scalingStats?.total ?? 0} />
          </div>
          <div className="flex justify-end">
            <button onClick={() => setShowPolicyForm(!showPolicyForm)} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">
              {showPolicyForm ? '取消' : '+ 新建策略'}
            </button>
          </div>
          {showPolicyForm && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 space-y-3">
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm text-gray-600 mb-1">Agent ID</label>
                  <input value={policyForm.agent_id} onChange={e => setPolicyForm({ ...policyForm, agent_id: e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm" placeholder="agent-1" />
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">Agent 名称</label>
                  <input value={policyForm.agent_name} onChange={e => setPolicyForm({ ...policyForm, agent_name: e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm" placeholder="客服助手" />
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">指标类型</label>
                  <select value={policyForm.metric_type} onChange={e => setPolicyForm({ ...policyForm, metric_type: e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm">
                    <option value="cpu_usage">CPU 使用率</option>
                    <option value="memory_usage">内存使用率</option>
                    <option value="qps">QPS</option>
                    <option value="token_rate">Token 速率</option>
                    <option value="p95_latency">P95 延迟</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">扩容阈值</label>
                  <input type="number" value={policyForm.scale_out_threshold} onChange={e => setPolicyForm({ ...policyForm, scale_out_threshold: +e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm" />
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">缩容阈值</label>
                  <input type="number" value={policyForm.scale_in_threshold} onChange={e => setPolicyForm({ ...policyForm, scale_in_threshold: +e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm" />
                </div>
                <div className="flex items-end gap-4">
                  <div>
                    <label className="block text-sm text-gray-600 mb-1">最小实例</label>
                    <input type="number" value={policyForm.min_instances} onChange={e => setPolicyForm({ ...policyForm, min_instances: +e.target.value })}
                      className="w-20 p-2 border border-gray-200 rounded-lg text-sm" />
                  </div>
                  <div>
                    <label className="block text-sm text-gray-600 mb-1">最大实例</label>
                    <input type="number" value={policyForm.max_instances} onChange={e => setPolicyForm({ ...policyForm, max_instances: +e.target.value })}
                      className="w-20 p-2 border border-gray-200 rounded-lg text-sm" />
                  </div>
                </div>
              </div>
              <button onClick={handleCreatePolicy} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">保存策略</button>
            </div>
          )}
          <section className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            <h3 className="font-semibold text-gray-800 mb-3">扩缩容策略</h3>
            <DataTable
              rows={policies}
              cols={[
                { key: 'agent_name', label: 'Agent' },
                { key: 'metric_type', label: '指标' },
                { key: 'scale_out_threshold', label: '扩容阈值' },
                { key: 'scale_in_threshold', label: '缩容阈值' },
                { key: 'min_instances', label: '最小', render: v => v },
                { key: 'max_instances', label: '最大', render: v => v },
                { key: 'enabled', label: '启用', render: v => (v ? '✅' : '❌') },
                { key: 'id', label: '操作', render: (_, row) => (
                  <button onClick={() => handleEvaluate(row)} className="text-xs text-blue-600 hover:underline">模拟评估</button>
                ) },
              ]}
            />
          </section>
          <section className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            <h3 className="font-semibold text-gray-800 mb-3">扩缩容事件</h3>
            <DataTable
              rows={scalingEvents}
              cols={[
                { key: 'agent_name', label: 'Agent' },
                { key: 'direction', label: '方向', render: v => (
                  <Badge text={v} map={{ scale_out: 'bg-green-100 text-green-700', scale_in: 'bg-orange-100 text-orange-700' }} />
                ) },
                { key: 'previous_instances', label: '原实例' },
                { key: 'new_instances', label: '新实例' },
                { key: 'metric_value', label: '指标值', render: v => (v != null ? v.toFixed(2) : '-') },
                { key: 'trigger_reason', label: '触发原因' },
                { key: 'created_at', label: '时间', render: v => fmtTime(v) },
              ]}
            />
          </section>
        </div>
      )}

      {/* ===== 日志管理 ===== */}
      {activeTab === 'logs' && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <StatCard title="24h 日志" value={logStats?.total ?? 0} />
            <StatCard title="DEBUG" value={logStats?.by_level?.debug ?? 0} />
            <StatCard title="INFO" value={logStats?.by_level?.info ?? 0} />
            <StatCard title="WARN" value={logStats?.by_level?.warn ?? 0} />
            <StatCard title="ERROR" value={logStats?.by_level?.error ?? 0} />
          </div>
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 space-y-3">
            <h3 className="font-semibold text-gray-800">日志搜索</h3>
            <div className="flex flex-wrap gap-3">
              <input value={logQuery.keyword} onChange={e => setLogQuery({ ...logQuery, keyword: e.target.value })}
                className="flex-1 min-w-[200px] p-2 border border-gray-200 rounded-lg text-sm" placeholder="搜索关键词..." />
              <select value={logQuery.level} onChange={e => setLogQuery({ ...logQuery, level: e.target.value })}
                className="p-2 border border-gray-200 rounded-lg text-sm">
                <option value="">全部级别</option>
                <option value="DEBUG">DEBUG</option>
                <option value="INFO">INFO</option>
                <option value="WARN">WARN</option>
                <option value="ERROR">ERROR</option>
              </select>
              <input value={logQuery.agent_id} onChange={e => setLogQuery({ ...logQuery, agent_id: e.target.value })}
                className="p-2 border border-gray-200 rounded-lg text-sm" placeholder="Agent ID" />
              <button onClick={fetchLogs} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">搜索</button>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 text-left text-gray-500">
                    <th className="py-2 pr-4">时间</th>
                    <th className="py-2 pr-4">级别</th>
                    <th className="py-2 pr-4">来源</th>
                    <th className="py-2 pr-4">Agent</th>
                    <th className="py-2">消息</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((l, i) => (
                    <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                      <td className="py-2 pr-4 text-gray-500 whitespace-nowrap">{fmtTime(l.timestamp)}</td>
                      <td className="py-2 pr-4"><Badge text={l.level} map={{ DEBUG: 'bg-gray-100 text-gray-600', INFO: 'bg-blue-100 text-blue-700', WARN: 'bg-yellow-100 text-yellow-700', ERROR: 'bg-red-100 text-red-700', FATAL: 'bg-red-200 text-red-800' }} /></td>
                      <td className="py-2 pr-4 text-gray-600">{l.source_type}</td>
                      <td className="py-2 pr-4 text-gray-600">{l.agent_id || '-'}</td>
                      <td className="py-2 text-gray-700 break-all">{l.message}</td>
                    </tr>
                  ))}
                  {logs.length === 0 && <tr><td colSpan={5} className="py-4 text-center text-gray-400">暂无日志</td></tr>}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ===== 定期维护 ===== */}
      {activeTab === 'maintenance' && (
        <div className="space-y-6">
          <div className="flex justify-end">
            <button onClick={() => setShowMaintForm(!showMaintForm)} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">
              {showMaintForm ? '取消' : '+ 新建维护任务'}
            </button>
          </div>
          {showMaintForm && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 space-y-3">
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm text-gray-600 mb-1">任务类型</label>
                  <select value={maintForm.task_type} onChange={e => setMaintForm({ ...maintForm, task_type: e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm">
                    <option value="session_cleanup">会话清理</option>
                    <option value="cache_cleanup">缓存清理</option>
                    <option value="temp_file_cleanup">临时文件清理</option>
                    <option value="index_rebuild">索引重建</option>
                    <option value="statistics_analysis">统计分析</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">任务名称</label>
                  <input value={maintForm.name} onChange={e => setMaintForm({ ...maintForm, name: e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm" placeholder="每日会话清理" />
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">定时表达式 (cron)</label>
                  <input value={maintForm.cron_expression} onChange={e => setMaintForm({ ...maintForm, cron_expression: e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm font-mono" placeholder="0 2 * * *" />
                </div>
              </div>
              <button onClick={handleCreateMaint} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">创建任务</button>
            </div>
          )}
          <section className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            <h3 className="font-semibold text-gray-800 mb-3">维护任务</h3>
            <DataTable
              rows={maintTasks}
              cols={[
                { key: 'name', label: '名称' },
                { key: 'task_type', label: '类型' },
                { key: 'cron_expression', label: '定时' },
                { key: 'enabled', label: '启用', render: v => (v ? '✅' : '❌') },
                { key: 'last_run_at', label: '上次执行', render: v => (v ? fmtTime(v) : '未执行') },
                { key: 'last_run_result', label: '上次结果' },
                { key: 'id', label: '操作', render: (_, row) => (
                  <div className="flex space-x-2">
                    <button onClick={() => handleRunMaint(row.id)} className="text-xs text-blue-600 hover:underline">立即执行</button>
                    <button onClick={() => updateMaintenanceTask(row.id, { enabled: !row.enabled }).then(fetchMaintenance)} className="text-xs text-gray-600 hover:underline">{row.enabled ? '停用' : '启用'}</button>
                    <button onClick={() => deleteMaintenanceTask(row.id).then(fetchMaintenance)} className="text-xs text-red-600 hover:underline">删除</button>
                  </div>
                ) },
              ]}
            />
          </section>
          <section className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            <h3 className="font-semibold text-gray-800 mb-3">执行记录</h3>
            <DataTable
              rows={maintExecs}
              cols={[
                { key: 'task_type', label: '类型' },
                { key: 'started_at', label: '开始', render: v => fmtTime(v) },
                { key: 'completed_at', label: '完成', render: v => (v ? fmtTime(v) : '-') },
                { key: 'status', label: '状态', render: v => <Badge text={v} map={{ running: 'bg-blue-100 text-blue-700', success: 'bg-green-100 text-green-700', failed: 'bg-red-100 text-red-700' }} /> },
                { key: 'items_processed', label: '处理项' },
                { key: 'items_cleaned', label: '清理项' },
                { key: 'duration_seconds', label: '耗时(s)', render: v => (v != null ? v.toFixed(1) : '-') },
              ]}
            />
          </section>
        </div>
      )}

      {/* ===== 异常自愈 ===== */}
      {activeTab === 'heal' && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard title="30天自愈事件" value={healStats?.total ?? 0} />
            <StatCard title="成功" value={healStats?.success ?? 0} />
            <StatCard title="失败" value={healStats?.failed ?? 0} />
            <StatCard title="成功率" value={healStats?.success_rate != null ? `${healStats.success_rate}%` : '-'} />
          </div>
          <div className="flex justify-end">
            <button onClick={() => setShowHealForm(!showHealForm)} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">
              {showHealForm ? '取消' : '+ 新建自愈规则'}
            </button>
          </div>
          {showHealForm && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 space-y-3">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <label className="block text-sm text-gray-600 mb-1">Agent ID</label>
                  <input value={healForm.agent_id} onChange={e => setHealForm({ ...healForm, agent_id: e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm" placeholder="agent-1" />
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">异常类型</label>
                  <select value={healForm.anomaly_type} onChange={e => setHealForm({ ...healForm, anomaly_type: e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm">
                    <option value="error_rate">错误率过高</option>
                    <option value="p99_latency">延迟过高</option>
                    <option value="health_drop">健康分骤降</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">自愈级别</label>
                  <select value={healForm.heal_level} onChange={e => setHealForm({ ...healForm, heal_level: e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm">
                    <option value="restart">L1 重启</option>
                    <option value="rollback">L2 回滚</option>
                    <option value="degrade">L3 降级</option>
                  </select>
                </div>
                <div className="flex items-end pb-1">
                  <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
                    <input type="checkbox" checked={healForm.auto_heal} onChange={e => setHealForm({ ...healForm, auto_heal: e.target.checked })} />
                    自动执行
                  </label>
                </div>
              </div>
              <button onClick={handleCreateHeal} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">创建规则</button>
            </div>
          )}
          <section className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            <h3 className="font-semibold text-gray-800 mb-3">自愈规则</h3>
            <DataTable
              rows={healRules}
              cols={[
                { key: 'agent_id', label: 'Agent' },
                { key: 'anomaly_type', label: '异常类型' },
                { key: 'heal_level', label: '级别', render: v => <Badge text={v} map={{ restart: 'bg-blue-100 text-blue-700', rollback: 'bg-orange-100 text-orange-700', degrade: 'bg-purple-100 text-purple-700' }} /> },
                { key: 'consecutive_threshold', label: '连续阈值' },
                { key: 'auto_heal', label: '自动', render: v => (v ? '✅' : '❌') },
                { key: 'enabled', label: '启用', render: v => (v ? '✅' : '❌') },
                { key: 'id', label: '操作', render: (_, row) => (
                  <button onClick={() => updateHealRule(row.id, { enabled: !row.enabled }).then(fetchHeal)} className="text-xs text-gray-600 hover:underline">{row.enabled ? '停用' : '启用'}</button>
                ) },
              ]}
            />
          </section>
          <section className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            <h3 className="font-semibold text-gray-800 mb-3">自愈记录</h3>
            <DataTable
              rows={healRecords}
              cols={[
                { key: 'agent_name', label: 'Agent' },
                { key: 'anomaly_type', label: '异常类型' },
                { key: 'anomaly_value', label: '异常值', render: v => (v != null ? v.toFixed(2) : '-') },
                { key: 'heal_level', label: '级别' },
                { key: 'status', label: '状态', render: v => <Badge text={v} map={{ detected: 'bg-gray-100 text-gray-600', healing: 'bg-blue-100 text-blue-700', verifying: 'bg-yellow-100 text-yellow-700', success: 'bg-green-100 text-green-700', failed: 'bg-red-100 text-red-700', escalated: 'bg-purple-100 text-purple-700' }} /> },
                { key: 'health_score_before', label: '健康分前', render: v => (v != null ? v.toFixed(1) : '-') },
                { key: 'health_score_after', label: '健康分后', render: v => (v != null ? v.toFixed(1) : '-') },
                { key: 'detected_at', label: '时间', render: v => fmtTime(v) },
              ]}
            />
          </section>
        </div>
      )}

      {/* ===== 运维报告 ===== */}
      {activeTab === 'reports' && (
        <div className="space-y-6">
          <div className="flex gap-3">
            <button onClick={() => handleGenerateReport('daily')} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">生成日报</button>
            <button onClick={() => handleGenerateReport('weekly')} className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700">生成周报</button>
            <button onClick={() => handleGenerateReport('monthly')} className="px-4 py-2 bg-purple-600 text-white text-sm rounded-lg hover:bg-purple-700">生成月报</button>
          </div>
          <section className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            <h3 className="font-semibold text-gray-800 mb-3">历史报告</h3>
            <DataTable
              rows={reports}
              cols={[
                { key: 'title', label: '标题' },
                { key: 'report_type', label: '类型', render: v => <Badge text={v} map={{ daily: 'bg-blue-100 text-blue-700', weekly: 'bg-indigo-100 text-indigo-700', monthly: 'bg-purple-100 text-purple-700' }} /> },
                { key: 'period_start', label: '开始', render: v => fmtTime(v) },
                { key: 'period_end', label: '结束', render: v => fmtTime(v) },
                { key: 'availability_rate', label: '可用率', render: v => (v != null ? `${v}%` : '-') },
                { key: 'anomaly_count', label: '异常' },
                { key: 'heal_count', label: '自愈' },
                { key: 'scaling_events', label: '扩缩容' },
                { key: 'generated_at', label: '生成时间', render: v => fmtTime(v) },
                { key: 'id', label: '操作', render: (_, row) => (
                  <button onClick={() => deleteReport(row.id).then(fetchReports)} className="text-xs text-red-600 hover:underline">删除</button>
                ) },
              ]}
            />
          </section>
        </div>
      )}
    </div>
  )
}

/* ==================== 小组件 ==================== */

function StatCard({ title, value, desc }: { title: string; value: any; desc?: string }) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
      <div className="text-sm text-gray-500">{title}</div>
      <div className="text-2xl font-bold text-gray-800 mt-1">{value}</div>
      {desc && <div className="text-xs text-gray-400 mt-1">{desc}</div>}
    </div>
  )
}

function Badge({ text, map }: { text: string; map?: Record<string, string> }) {
  const cls = (map && map[text]) || 'bg-gray-100 text-gray-700'
  return <span className={`inline-block px-2 py-0.5 rounded-full text-xs ${cls}`}>{text}</span>
}

function DataTable({ rows, cols }: { rows: Row[]; cols: { key: string; label: string; render?: (v: any, row: Row) => any }[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-100 text-left text-gray-500">
            {cols.map(c => <th key={c.key} className="py-2 pr-4 whitespace-nowrap">{c.label}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={row.id || i} className="border-b border-gray-50 hover:bg-gray-50">
              {cols.map(c => (
                <td key={c.key} className="py-2 pr-4 text-gray-700 whitespace-nowrap">
                  {c.render ? c.render(row[c.key], row) : (row[c.key] != null ? String(row[c.key]) : '-')}
                </td>
              ))}
            </tr>
          ))}
          {rows.length === 0 && <tr><td colSpan={cols.length} className="py-4 text-center text-gray-400">暂无数据</td></tr>}
        </tbody>
      </table>
    </div>
  )
}

function MiniTable({ rows, cols }: { rows: Row[]; cols: { key: string; label: string; render?: (v: any, row: Row) => any }[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-100 text-left text-gray-500">
            {cols.map(c => <th key={c.key} className="py-1.5 pr-3 whitespace-nowrap">{c.label}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={row.id || i} className="border-b border-gray-50">
              {cols.map(c => (
                <td key={c.key} className="py-1.5 pr-3 text-gray-700 whitespace-nowrap">
                  {c.render ? c.render(row[c.key], row) : (row[c.key] != null ? String(row[c.key]) : '-')}
                </td>
              ))}
            </tr>
          ))}
          {rows.length === 0 && <tr><td colSpan={cols.length} className="py-3 text-center text-gray-400 text-xs">暂无数据</td></tr>}
        </tbody>
      </table>
    </div>
  )
}

function fmtTime(v: any): string {
  if (!v) return '-'
  const d = new Date(v)
  if (isNaN(d.getTime())) return String(v)
  return d.toLocaleString('zh-CN', { hour12: false })
}
