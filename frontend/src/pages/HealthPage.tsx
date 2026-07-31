import { useState, useEffect, useCallback } from 'react'
import {
  runHealthCheck, listCheckRuns,
  listSnapshots, getTop5Healthy, getTop5Unhealthy, getHealthTrend, getHealthOverview, listHealthEvents,
  listWeightTemplates, createWeightTemplate, deleteWeightTemplate,
  listHealthConfigs, upsertHealthConfig, deleteHealthConfig,
  compareAgentsHealth,
} from '../api/health'

const STATUS_COLORS: Record<string, string> = {
  healthy: 'bg-green-100 text-green-700',
  degraded: 'bg-yellow-100 text-yellow-700',
  unhealthy: 'bg-red-100 text-red-700',
  offline: 'bg-gray-100 text-gray-600',
}

const CHECK_COLORS: Record<string, string> = {
  pass: 'bg-green-100 text-green-700',
  degraded: 'bg-yellow-100 text-yellow-700',
  fail: 'bg-red-100 text-red-700',
}

const TABS = [
  { key: 'overview', label: '健康面板' },
  { key: 'checks', label: '检查记录' },
  { key: 'weights', label: '评分权重' },
  { key: 'configs', label: '检查配置' },
  { key: 'compare', label: '雷达对比' },
]

interface Row { id: string; [key: string]: any }

export default function HealthPage() {
  const [activeTab, setActiveTab] = useState('overview')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  // overview
  const [overview, setOverview] = useState<any>(null)
  const [snapshots, setSnapshots] = useState<Row[]>([])
  const [top5Healthy, setTop5Healthy] = useState<Row[]>([])
  const [top5Unhealthy, setTop5Unhealthy] = useState<Row[]>([])
  const [trend, setTrend] = useState<any[]>([])
  const [events, setEvents] = useState<Row[]>([])
  const [checkAgentId, setCheckAgentId] = useState('')
  const [checking, setChecking] = useState(false)

  // checks
  const [checkRuns, setCheckRuns] = useState<Row[]>([])

  // weights
  const [weights, setWeights] = useState<Row[]>([])
  const [showWeightForm, setShowWeightForm] = useState(false)
  const [weightForm, setWeightForm] = useState<any>({
    template_name: '', weight_response_time: 30, weight_token: 20, weight_error_rate: 25,
    weight_session_success: 15, weight_dependency: 10, is_default: false,
  })

  // configs
  const [configs, setConfigs] = useState<Row[]>([])
  const [showConfigForm, setShowConfigForm] = useState(false)
  const [configForm, setConfigForm] = useState<any>({
    agent_id: '', l1_interval_sec: 10, l2_interval_sec: 30, l3_interval_sec: 300, l4_interval_sec: 900,
    l3_skills: [], l3_mcp_servers: [], auto_restart_on_l1_fail: true, enabled: true,
  })

  // compare
  const [compareInput, setCompareInput] = useState('')
  const [compareResult, setCompareResult] = useState<Row[]>([])

  const fetchOverview = useCallback(async () => {
    try {
      const [o, s, t5h, t5u, tr, ev] = await Promise.all([
        getHealthOverview(), listSnapshots({ limit: 100 }),
        getTop5Healthy(), getTop5Unhealthy(), getHealthTrend({ hours: 24 }), listHealthEvents({ limit: 20 }),
      ])
      setOverview(o.data)
      setSnapshots(s.data?.items || [])
      setTop5Healthy(t5h.data?.items || [])
      setTop5Unhealthy(t5u.data?.items || [])
      setTrend(tr.data?.items || [])
      setEvents(ev.data?.items || [])
    } catch (e: any) { setError(e?.message || '加载健康数据失败') }
  }, [])

  const fetchChecks = useCallback(async () => {
    try { setCheckRuns((await listCheckRuns({ limit: 100 })).data?.items || []) } catch (e: any) { setError(e?.message || '加载检查记录失败') }
  }, [])

  const fetchWeights = useCallback(async () => {
    try { setWeights((await listWeightTemplates()).data?.items || []) } catch (e: any) { setError(e?.message || '加载权重失败') }
  }, [])

  const fetchConfigs = useCallback(async () => {
    try { setConfigs((await listHealthConfigs({ limit: 50 })).data?.items || []) } catch (e: any) { setError(e?.message || '加载配置失败') }
  }, [])

  useEffect(() => {
    setLoading(true)
    Promise.all([fetchOverview(), fetchChecks(), fetchWeights(), fetchConfigs()])
      .finally(() => setLoading(false))
  }, [fetchOverview, fetchChecks, fetchWeights, fetchConfigs])

  const handleRunCheck = async () => {
    if (!checkAgentId) { setError('请输入 Agent ID'); return }
    setChecking(true)
    try {
      const r = await runHealthCheck({ agent_id: checkAgentId, agent_name: checkAgentId, metrics: { p95_ms: 800, token_usage_ratio: 0.85, error_rate: 0.003, session_success_rate: 0.99 } })
      setSuccess(`检查完成: 评分 ${r.data?.data?.score}，状态 ${r.data?.data?.status}`)
      setCheckAgentId('')
      fetchOverview()
    } catch (e: any) { setError(e?.message || '检查失败') }
    finally { setChecking(false) }
  }

  const handleSaveWeight = async () => {
    try {
      await createWeightTemplate({ ...weightForm, description: weightForm.template_name })
      setSuccess('权重模板已保存')
      setShowWeightForm(false)
      setWeightForm({ template_name: '', weight_response_time: 30, weight_token: 20, weight_error_rate: 25, weight_session_success: 15, weight_dependency: 10, is_default: false })
      fetchWeights()
    } catch (e: any) { setError(e?.message || '保存权重失败') }
  }

  const handleSaveConfig = async () => {
    try {
      await upsertHealthConfig(configForm)
      setSuccess('检查配置已保存')
      setShowConfigForm(false)
      setConfigForm({ agent_id: '', l1_interval_sec: 10, l2_interval_sec: 30, l3_interval_sec: 300, l4_interval_sec: 900, l3_skills: [], l3_mcp_servers: [], auto_restart_on_l1_fail: true, enabled: true })
      fetchConfigs()
    } catch (e: any) { setError(e?.message || '保存配置失败') }
  }

  const handleCompare = async () => {
    const ids = compareInput.split(',').map(s => s.trim()).filter(Boolean)
    if (ids.length < 2) { setError('请至少输入 2 个 Agent ID'); return }
    try {
      setCompareResult((await compareAgentsHealth(ids)).data?.items || [])
    } catch (e: any) { setError(e?.message || '对比失败') }
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">各智能体健康监控</h1>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg">
          {error}
          <button onClick={() => setError('')} className="ml-2 text-xs underline">关闭</button>
        </div>
      )}
      {success && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 text-green-700 text-sm rounded-lg">
          {success}
          <button onClick={() => setSuccess('')} className="ml-2 text-xs underline">关闭</button>
        </div>
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

      {/* ===== 健康面板 ===== */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
            <StatCard title="Agent 总数" value={overview?.total_agents ?? '-'} />
            <StatCard title="健康(绿)" value={overview?.healthy ?? '-'} color="text-green-600" />
            <StatCard title="亚健康(黄)" value={overview?.degraded ?? '-'} color="text-yellow-600" />
            <StatCard title="不健康(红)" value={overview?.unhealthy ?? '-'} color="text-red-600" />
            <StatCard title="离线(灰)" value={overview?.offline ?? '-'} color="text-gray-600" />
            <StatCard title="平台健康分" value={overview?.platform_score ?? '-'} />
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 space-y-3">
            <h3 className="font-semibold text-gray-800">手动健康检查</h3>
            <div className="flex gap-3">
              <input value={checkAgentId} onChange={e => setCheckAgentId(e.target.value)}
                className="flex-1 p-2 border border-gray-200 rounded-lg text-sm" placeholder="输入 Agent ID 执行 L1-L4 检查" />
              <button onClick={handleRunCheck} disabled={checking}
                className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50">
                {checking ? '检查中...' : '执行检查'}
              </button>
            </div>
          </div>

          <section className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            <h3 className="font-semibold text-gray-800 mb-3">Agent 健康列表</h3>
            <DataTable
              rows={snapshots}
              cols={[
                { key: 'agent_name', label: 'Agent' },
                { key: 'status', label: '状态', render: v => <Badge text={v} map={STATUS_COLORS} /> },
                { key: 'score', label: '健康分', render: v => <ScoreBar v={v} /> },
                { key: 'l1_status', label: 'L1存活', render: v => <Badge text={v} map={CHECK_COLORS} /> },
                { key: 'l2_status', label: 'L2就绪', render: v => <Badge text={v} map={CHECK_COLORS} /> },
                { key: 'l3_status', label: 'L3能力', render: v => <Badge text={v} map={CHECK_COLORS} /> },
                { key: 'l4_status', label: 'L4链路', render: v => <Badge text={v} map={CHECK_COLORS} /> },
                { key: 'last_checked_at', label: '上次检查', render: v => fmtTime(v) },
              ]}
            />
          </section>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <section className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <h3 className="font-semibold text-gray-800 mb-3">🏆 Top5 健康 Agent</h3>
              <DataTable
                rows={top5Healthy}
                cols={[
                  { key: 'agent_name', label: 'Agent' },
                  { key: 'score', label: '健康分', render: v => <ScoreBar v={v} /> },
                  { key: 'status', label: '状态', render: v => <Badge text={v} map={STATUS_COLORS} /> },
                ]}
              />
            </section>
            <section className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <h3 className="font-semibold text-gray-800 mb-3">⚠️ Top5 需关注 Agent</h3>
              <DataTable
                rows={top5Unhealthy}
                cols={[
                  { key: 'agent_name', label: 'Agent' },
                  { key: 'score', label: '健康分', render: v => <ScoreBar v={v} /> },
                  { key: 'status', label: '状态', render: v => <Badge text={v} map={STATUS_COLORS} /> },
                ]}
              />
            </section>
          </div>

          <section className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            <h3 className="font-semibold text-gray-800 mb-3">24h 健康趋势（全平台）</h3>
            <TrendChart data={trend} />
          </section>

          <section className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            <h3 className="font-semibold text-gray-800 mb-3">最近健康事件</h3>
            <DataTable
              rows={events}
              cols={[
                { key: 'agent_name', label: 'Agent' },
                { key: 'level', label: '级别', render: v => <Badge text={v} map={{ info: 'bg-blue-100 text-blue-700', warning: 'bg-yellow-100 text-yellow-700', critical: 'bg-red-100 text-red-700' }} /> },
                { key: 'message', label: '消息' },
                { key: 'score_after', label: '当前评分', render: v => (v != null ? v : '-') },
                { key: 'created_at', label: '时间', render: v => fmtTime(v) },
              ]}
            />
          </section>
        </div>
      )}

      {/* ===== 检查记录 ===== */}
      {activeTab === 'checks' && (
        <section className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <h3 className="font-semibold text-gray-800 mb-3">检查执行记录</h3>
          <DataTable
            rows={checkRuns}
            cols={[
              { key: 'agent_name', label: 'Agent' },
              { key: 'level', label: '级别', render: v => <Badge text={v} map={{ l1_alive: 'bg-blue-100 text-blue-700', l2_ready: 'bg-indigo-100 text-indigo-700', l3_capability: 'bg-purple-100 text-purple-700', l4_e2e: 'bg-pink-100 text-pink-700' }} /> },
              { key: 'status', label: '结果', render: v => <Badge text={v} map={CHECK_COLORS} /> },
              { key: 'latency_ms', label: '耗时(ms)', render: v => (v != null ? v.toFixed(1) : '-') },
              { key: 'error_message', label: '错误', render: v => (v ? <span className="text-red-600">{v}</span> : '-') },
              { key: 'checked_at', label: '时间', render: v => fmtTime(v) },
            ]}
          />
        </section>
      )}

      {/* ===== 评分权重 ===== */}
      {activeTab === 'weights' && (
        <div className="space-y-6">
          <div className="flex justify-end">
            <button onClick={() => setShowWeightForm(!showWeightForm)} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">
              {showWeightForm ? '取消' : '+ 新建权重模板'}
            </button>
          </div>
          {showWeightForm && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 space-y-3">
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm text-gray-600 mb-1">模板名称</label>
                  <input value={weightForm.template_name} onChange={e => setWeightForm({ ...weightForm, template_name: e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm" placeholder="标准模板" />
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">响应时间权重 %</label>
                  <input type="number" value={weightForm.weight_response_time} onChange={e => setWeightForm({ ...weightForm, weight_response_time: +e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm" />
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">Token 权重 %</label>
                  <input type="number" value={weightForm.weight_token} onChange={e => setWeightForm({ ...weightForm, weight_token: +e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm" />
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">错误率权重 %</label>
                  <input type="number" value={weightForm.weight_error_rate} onChange={e => setWeightForm({ ...weightForm, weight_error_rate: +e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm" />
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">会话成功率权重 %</label>
                  <input type="number" value={weightForm.weight_session_success} onChange={e => setWeightForm({ ...weightForm, weight_session_success: +e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm" />
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">依赖健康权重 %</label>
                  <input type="number" value={weightForm.weight_dependency} onChange={e => setWeightForm({ ...weightForm, weight_dependency: +e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm" />
                </div>
              </div>
              <label className="flex items-center gap-2 text-sm text-gray-600">
                <input type="checkbox" checked={weightForm.is_default} onChange={e => setWeightForm({ ...weightForm, is_default: e.target.checked })} />
                设为默认模板
              </label>
              <button onClick={handleSaveWeight} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">保存模板</button>
            </div>
          )}
          <section className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            <h3 className="font-semibold text-gray-800 mb-3">权重模板</h3>
            <DataTable
              rows={weights}
              cols={[
                { key: 'template_name', label: '名称' },
                { key: 'weight_response_time', label: '响应%' },
                { key: 'weight_token', label: 'Token%' },
                { key: 'weight_error_rate', label: '错误%' },
                { key: 'weight_session_success', label: '会话%' },
                { key: 'weight_dependency', label: '依赖%' },
                { key: 'is_default', label: '默认', render: v => (v ? '⭐' : '') },
                { key: 'enabled', label: '启用', render: v => (v ? '✅' : '❌') },
                { key: 'id', label: '操作', render: (_, row) => (
                  <button onClick={() => deleteWeightTemplate(row.id).then(fetchWeights)} className="text-xs text-red-600 hover:underline">停用</button>
                ) },
              ]}
            />
          </section>
        </div>
      )}

      {/* ===== 检查配置 ===== */}
      {activeTab === 'configs' && (
        <div className="space-y-6">
          <div className="flex justify-end">
            <button onClick={() => setShowConfigForm(!showConfigForm)} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">
              {showConfigForm ? '取消' : '+ 新建检查配置'}
            </button>
          </div>
          {showConfigForm && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 space-y-3">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <label className="block text-sm text-gray-600 mb-1">Agent ID</label>
                  <input value={configForm.agent_id} onChange={e => setConfigForm({ ...configForm, agent_id: e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm" />
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">L1 间隔(秒)</label>
                  <input type="number" value={configForm.l1_interval_sec} onChange={e => setConfigForm({ ...configForm, l1_interval_sec: +e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm" />
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">L2 间隔(秒)</label>
                  <input type="number" value={configForm.l2_interval_sec} onChange={e => setConfigForm({ ...configForm, l2_interval_sec: +e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm" />
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">L3 间隔(秒)</label>
                  <input type="number" value={configForm.l3_interval_sec} onChange={e => setConfigForm({ ...configForm, l3_interval_sec: +e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm" />
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">L4 间隔(秒)</label>
                  <input type="number" value={configForm.l4_interval_sec} onChange={e => setConfigForm({ ...configForm, l4_interval_sec: +e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm" />
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">就绪端点</label>
                  <input value={configForm.ready_endpoint || ''} onChange={e => setConfigForm({ ...configForm, ready_endpoint: e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm" placeholder="/health/ready" />
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">L3 Skills (逗号分隔)</label>
                  <input value={(configForm.l3_skills || []).join(',')} onChange={e => setConfigForm({ ...configForm, l3_skills: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm" placeholder="web_search,code_runner" />
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">L3 MCP (逗号分隔)</label>
                  <input value={(configForm.l3_mcp_servers || []).join(',')} onChange={e => setConfigForm({ ...configForm, l3_mcp_servers: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm" placeholder="qdrant,redis" />
                </div>
              </div>
              <button onClick={handleSaveConfig} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">保存配置</button>
            </div>
          )}
          <section className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            <h3 className="font-semibold text-gray-800 mb-3">检查配置列表</h3>
            <DataTable
              rows={configs}
              cols={[
                { key: 'agent_id', label: 'Agent' },
                { key: 'l1_interval_sec', label: 'L1(s)' },
                { key: 'l2_interval_sec', label: 'L2(s)' },
                { key: 'l3_interval_sec', label: 'L3(s)' },
                { key: 'l4_interval_sec', label: 'L4(s)' },
                { key: 'ready_endpoint', label: '就绪端点', render: v => (v || '-') },
                { key: 'auto_restart_on_l1_fail', label: '自动重启', render: v => (v ? '✅' : '❌') },
                { key: 'enabled', label: '启用', render: v => (v ? '✅' : '❌') },
                { key: 'agent_id', label: '操作', render: (_, row) => (
                  <button onClick={() => deleteHealthConfig(row.agent_id).then(fetchConfigs)} className="text-xs text-red-600 hover:underline">停用</button>
                ) },
              ]}
            />
          </section>
        </div>
      )}

      {/* ===== 雷达对比 ===== */}
      {activeTab === 'compare' && (
        <div className="space-y-6">
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 space-y-3">
            <h3 className="font-semibold text-gray-800">Agent 健康对比（雷达）</h3>
            <div className="flex gap-3">
              <input value={compareInput} onChange={e => setCompareInput(e.target.value)}
                className="flex-1 p-2 border border-gray-200 rounded-lg text-sm" placeholder="输入 Agent ID，逗号分隔，至少 2 个 (如: agent-1,agent-2)" />
              <button onClick={handleCompare} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">对比</button>
            </div>
          </div>
          {compareResult.length > 0 && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <section className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
                <h3 className="font-semibold text-gray-800 mb-3">雷达图</h3>
                <RadarChart data={compareResult} />
              </section>
              <section className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
                <h3 className="font-semibold text-gray-800 mb-3">维度明细</h3>
                <DataTable
                  rows={compareResult}
                  cols={[
                    { key: 'agent_name', label: 'Agent' },
                    { key: 'score', label: '总分' },
                    { key: 'status', label: '状态', render: v => <Badge text={v} map={STATUS_COLORS} /> },
                    { key: 'dimensions.response_time', label: '响应', render: v => v },
                    { key: 'dimensions.token', label: 'Token', render: v => v },
                    { key: 'dimensions.error_rate', label: '错误率', render: v => v },
                    { key: 'dimensions.session_success', label: '会话', render: v => v },
                    { key: 'dimensions.dependency', label: '依赖', render: v => v },
                  ]}
                />
              </section>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/* ==================== 小组件 ==================== */

function StatCard({ title, value, desc, color }: { title: string; value: any; desc?: string; color?: string }) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
      <div className="text-sm text-gray-500">{title}</div>
      <div className={`text-2xl font-bold mt-1 ${color || 'text-gray-800'}`}>{value}</div>
      {desc && <div className="text-xs text-gray-400 mt-1">{desc}</div>}
    </div>
  )
}

function Badge({ text, map }: { text: string; map?: Record<string, string> }) {
  const cls = (map && map[text]) || 'bg-gray-100 text-gray-700'
  return <span className={`inline-block px-2 py-0.5 rounded-full text-xs ${cls}`}>{text}</span>
}

function ScoreBar({ v }: { v: number }) {
  const color = v >= 80 ? 'bg-green-500' : v >= 60 ? 'bg-yellow-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-2 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full ${color}`} style={{ width: `${Math.min(100, v || 0)}%` }} />
      </div>
      <span className="text-xs text-gray-600">{v ?? '-'}</span>
    </div>
  )
}

function TrendChart({ data }: { data: { time: string; score: number }[] }) {
  const maxScore = 100
  const points = data.map((d, i) => {
    const x = (i / Math.max(data.length - 1, 1)) * 500 + 20
    const y = 90 - ((d.score / maxScore) * 70)
    return { x, y, ...d }
  })
  if (points.length === 0) {
    return <div className="text-center text-gray-400 text-sm py-8">暂无趋势数据</div>
  }
  const path = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')

  return (
    <div>
      <svg viewBox="0 0 540 120" className="w-full">
        {[0, 25, 50, 75, 100].map(v => {
          const y = 90 - ((v / maxScore) * 70)
          return <g key={v}>
            <line x1="20" y1={y} x2="520" y2={y} stroke="#f3f4f6" strokeWidth="1" />
            <text x="2" y={y + 3} fontSize="9" fill="#9ca3af">{v}</text>
          </g>
        })}
        <path d={path} fill="none" stroke="#3b82f6" strokeWidth="2" />
        {points.map((p, i) => <circle key={i} cx={p.x} cy={p.y} r="2.5" fill="#3b82f6" />)}
      </svg>
      <div className="flex justify-between text-xs text-gray-400 mt-1">
        <span>{points[0]?.time}</span>
        <span>{points[points.length - 1]?.time}</span>
      </div>
    </div>
  )
}

function RadarChart({ data }: { data: Row[] }) {
  const dims = ['response_time', 'token', 'error_rate', 'session_success', 'dependency']
  const labels: Record<string, string> = { response_time: '响应', token: 'Token', error_rate: '错误率', session_success: '会话', dependency: '依赖' }
  const colors = ['#3b82f6', '#ef4444', '#22c55e', '#f59e0b', '#8b5cf6']
  const cx = 130, cy = 110, R = 80

  const angleFor = (i: number) => (Math.PI * 2 * i / dims.length) - Math.PI / 2
  const pointAt = (i: number, val: number) => ({
    x: cx + Math.cos(angleFor(i)) * R * val / 100,
    y: cy + Math.sin(angleFor(i)) * R * val / 100,
  })

  return (
    <svg viewBox="0 0 260 220" className="w-full max-w-sm mx-auto">
      {/* 网格 */}
      {[25, 50, 75, 100].map(level => (
        <polygon key={level} points={dims.map((_, i) => {
          const p = pointAt(i, level)
          return `${p.x},${p.y}`
        }).join(' ')} fill="none" stroke="#e5e7eb" strokeWidth="1" />
      ))}
      {/* 轴线 */}
      {dims.map((_, i) => {
        const p = pointAt(i, 100)
        return <line key={i} x1={cx} y1={cy} x2={p.x} y2={p.y} stroke="#e5e7eb" strokeWidth="1" />
      })}
      {/* 标签 */}
      {dims.map((d, i) => {
        const p = pointAt(i, 112)
        return <text key={d} x={p.x} y={p.y} fontSize="10" fill="#6b7280" textAnchor="middle">{labels[d]}</text>
      })}
      {/* 数据多边形 */}
      {data.map((agent, ai) => (
        <polygon key={ai} points={dims.map((d, i) => {
          const val = agent.dimensions?.[d] ?? 0
          const p = pointAt(i, val)
          return `${p.x},${p.y}`
        }).join(' ')} fill={colors[ai % colors.length]} fillOpacity="0.15" stroke={colors[ai % colors.length]} strokeWidth="2" />
      ))}
      {/* 图例 */}
      {data.map((agent, ai) => (
        <g key={ai}>
          <rect x={10} y={190 + ai * 14} width="10" height="10" fill={colors[ai % colors.length]} />
          <text x={25} y={199 + ai * 14} fontSize="10" fill="#374151">{agent.agent_name} ({agent.score})</text>
        </g>
      ))}
    </svg>
  )
}

function DataTable({ rows, cols }: { rows: Row[]; cols: { key: string; label: string; render?: (v: any, row: Row) => any }[] }) {
  const getVal = (row: Row, key: string) => {
    if (key.includes('.')) {
      return key.split('.').reduce((o, k) => (o ? o[k] : undefined), row)
    }
    return row[key]
  }
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
              {cols.map(c => {
                const val = getVal(row, c.key)
                return (
                  <td key={c.key} className="py-2 pr-4 text-gray-700 whitespace-nowrap">
                    {c.render ? c.render(val, row) : (val != null ? String(val) : '-')}
                  </td>
                )
              })}
            </tr>
          ))}
          {rows.length === 0 && <tr><td colSpan={cols.length} className="py-4 text-center text-gray-400">暂无数据</td></tr>}
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
