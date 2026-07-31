import { useState, useEffect, useCallback } from 'react'
import {
  getTokenStats, recordTokenUsage, listTokenUsage,
  getTokenBudget, updateTokenBudget, listTokenAlerts, updateTokenAlert,
  optimizeContext, suggestModel, getCascadePlan, listCascadeRules, saveCascadeRule,
  getTokenEffectiveness,
} from '../api/tokens'

const TABS = [
  { key: 'overview', label: '统计总览' },
  { key: 'budget', label: '预算/配额' },
  { key: 'optimize', label: '优化策略' },
  { key: 'effect', label: '效果评估' },
  { key: 'usage', label: '用量明细' },
]

const TASK_TYPES = ['chat', 'code', 'analysis', 'writing', 'translation']

function fmtNum(n?: number) {
  if (n == null) return '0'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return String(n)
}

export default function TokenPage() {
  const [activeTab, setActiveTab] = useState('overview')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  // 统计
  const [stats, setStats] = useState<any>(null)
  const [days, setDays] = useState(30)

  // 预算
  const [budgetUserId, setBudgetUserId] = useState('user-001')
  const [budget, setBudget] = useState<any>(null)
  const [budgetForm, setBudgetForm] = useState<any>({})

  // 告警
  const [alerts, setAlerts] = useState<any[]>([])

  // 优化
  const [taskType, setTaskType] = useState('chat')
  const [suggestion, setSuggestion] = useState<any>(null)
  const [cascadePlan, setCascadePlan] = useState<any>(null)
  const [cascadeRules, setCascadeRules] = useState<any[]>([])
  const [sampleText, setSampleText] = useState('这是一段用于测试上下文裁剪优化的示例文本，请确保系统提示与最近消息被保留。')
  const [optResult, setOptResult] = useState<any>(null)

  // 效果
  const [effect, setEffect] = useState<any>(null)

  // 明细
  const [usageItems, setUsageItems] = useState<any[]>([])
  const [usageTotal, setUsageTotal] = useState(0)
  const [usagePage, setUsagePage] = useState(1)

  const fetchStats = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const res = await getTokenStats({ days })
      setStats(res.data)
    } catch (e: any) { setError(e?.response?.data?.detail || '加载统计失败') } finally { setLoading(false) }
  }, [days])
  useEffect(() => { fetchStats() }, [fetchStats])

  const fetchBudget = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const res = await getTokenBudget(budgetUserId)
      setBudget(res.data)
      setBudgetForm(res.data)
      const ares = await listTokenAlerts({ user_id: budgetUserId })
      setAlerts(ares.data || [])
    } catch (e: any) { setError(e?.response?.data?.detail || '加载预算失败') } finally { setLoading(false) }
  }, [budgetUserId])
  useEffect(() => { if (activeTab === 'budget') fetchBudget() }, [activeTab, fetchBudget])

  const fetchOptimize = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const s = await suggestModel(taskType)
      setSuggestion(s.data)
      const c = await getCascadePlan(taskType)
      setCascadePlan(c.data)
      const r = await listCascadeRules()
      setCascadeRules(r.data || [])
    } catch (e: any) { setError(e?.response?.data?.detail || '加载优化策略失败') } finally { setLoading(false) }
  }, [taskType])
  useEffect(() => { if (activeTab === 'optimize') fetchOptimize() }, [activeTab, fetchOptimize])

  const fetchEffect = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const res = await getTokenEffectiveness(days)
      setEffect(res.data)
    } catch (e: any) { setError(e?.response?.data?.detail || '加载效果评估失败') } finally { setLoading(false) }
  }, [days])
  useEffect(() => { if (activeTab === 'effect') fetchEffect() }, [activeTab, fetchEffect])

  const fetchUsage = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const res = await listTokenUsage({ page: usagePage, page_size: 20 })
      setUsageItems(res.data.items || [])
      setUsageTotal(res.data.total || 0)
    } catch (e: any) { setError(e?.response?.data?.detail || '加载明细失败') } finally { setLoading(false) }
  }, [usagePage])
  useEffect(() => { if (activeTab === 'usage') fetchUsage() }, [activeTab, fetchUsage])

  // 操作
  const saveBudget = async () => {
    setLoading(true); setError('')
    try {
      const res = await updateTokenBudget({ user_id: budgetUserId, ...budgetForm })
      setBudget(res.data)
      setSuccess('预算配置已保存')
    } catch (e: any) { setError(e?.response?.data?.detail || '保存失败') } finally { setLoading(false) }
  }

  const doRecord = async () => {
    setLoading(true); setError(''); setSuccess('')
    try {
      await recordTokenUsage({
        user_id: budgetUserId, model_name: 'gpt-4o-mini',
        input_tokens: 1500, output_tokens: 800,
      })
      setSuccess('测试用量已记录')
      fetchStats()
    } catch (e: any) { setError(e?.response?.data?.detail || '记录失败') } finally { setLoading(false) }
  }

  const doOptimize = async () => {
    setLoading(true); setError('')
    try {
      const res = await optimizeContext({
        messages: [
          { role: 'system', content: '你是一个智能助手，请保持简洁。' },
          { role: 'user', content: sampleText },
          { role: 'assistant', content: '好的，我会保持简洁的回答。' },
        ],
        max_tokens: 100,
      })
      setOptResult(res.data)
      setSuccess('上下文裁剪完成')
    } catch (e: any) { setError(e?.response?.data?.detail || '优化失败') } finally { setLoading(false) }
  }

  const saveCascade = async (type: string) => {
    setLoading(true); setError('')
    try {
      await saveCascadeRule({
        task_type: type, primary_model: 'gpt-4o',
        fallback_chain: ['gpt-4o-mini', 'deepseek-chat'],
        max_input_tokens: 8000, enabled: true,
      })
      setSuccess(`级联规则 ${type} 已保存`)
      fetchOptimize()
    } catch (e: any) { setError(e?.response?.data?.detail || '保存失败') } finally { setLoading(false) }
  }

  const inputCls = 'border border-gray-300 rounded px-2 py-1 text-sm w-full'
  const btnCls = 'px-3 py-1.5 rounded text-sm bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50'
  const btnSec = 'px-3 py-1.5 rounded text-sm border border-gray-300 hover:bg-gray-50'

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Token 使用管理与优化</h1>
          <p className="text-sm text-gray-500 mt-1">4.16 · 成本控制 · 预算告警 · 模型级联 · 上下文优化 · 效果评估</p>
        </div>
        <button className={btnSec} onClick={doRecord} disabled={loading}>写入测试用量</button>
      </div>

      {error && <div className="bg-red-50 text-red-700 border border-red-200 rounded px-4 py-2 mb-4 text-sm">{error}</div>}
      {success && <div className="bg-green-50 text-green-700 border border-green-200 rounded px-4 py-2 mb-4 text-sm">{success}</div>}

      <div className="flex gap-1 mb-4 flex-wrap">
        {TABS.map(t => (
          <button key={t.key} onClick={() => { setActiveTab(t.key); setSuccess('') }}
            className={`px-4 py-2 rounded-t text-sm ${activeTab === t.key ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* ============ 统计总览 ============ */}
      {activeTab === 'overview' && stats && (
        <div>
          <div className="flex items-center gap-3 mb-4">
            <span className="text-sm text-gray-600">统计周期</span>
            <select className={inputCls} style={{ width: 140 }} value={days} onChange={e => setDays(Number(e.target.value))}>
              <option value={7}>近 7 天</option>
              <option value={30}>近 30 天</option>
              <option value={90}>近 90 天</option>
            </select>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            <div className="bg-white border rounded p-4">
              <div className="text-2xl font-bold text-blue-700">{fmtNum(stats.total_tokens)}</div>
              <div className="text-xs text-gray-500 mt-1">总 Token（输入+输出）</div>
            </div>
            <div className="bg-white border rounded p-4">
              <div className="text-2xl font-bold text-green-700">${stats.total_cost?.toFixed(4)}</div>
              <div className="text-xs text-gray-500 mt-1">总成本（USD）</div>
            </div>
            <div className="bg-white border rounded p-4">
              <div className="text-2xl font-bold text-purple-700">{fmtNum(stats.cached_tokens)}</div>
              <div className="text-xs text-gray-500 mt-1">缓存命中 Token</div>
            </div>
            <div className="bg-white border rounded p-4">
              <div className="text-2xl font-bold text-orange-700">{fmtNum(stats.compressed_tokens)}</div>
              <div className="text-xs text-gray-500 mt-1">上下文裁剪节省</div>
            </div>
          </div>

          <div className="grid md:grid-cols-2 gap-4">
            <div className="bg-white border rounded p-4">
              <h3 className="font-semibold mb-3">模型级别分布</h3>
              <table className="w-full text-sm">
                <thead className="text-left text-xs text-gray-500">
                  <tr><th className="py-1">模型</th><th className="py-1">调用</th><th className="py-1">Token</th><th className="py-1">成本</th></tr>
                </thead>
                <tbody>
                  {stats.by_model?.map((m: any, i: number) => (
                    <tr key={i} className="border-t">
                      <td className="py-1.5 font-mono text-xs">{m.model}</td>
                      <td className="py-1.5">{m.calls}</td>
                      <td className="py-1.5">{fmtNum(m.input_tokens + m.output_tokens)}</td>
                      <td className="py-1.5">${m.cost?.toFixed(4)}</td>
                    </tr>
                  ))}
                  {(!stats.by_model || stats.by_model.length === 0) && (
                    <tr><td colSpan={4} className="py-4 text-center text-gray-400 text-xs">暂无数据</td></tr>
                  )}
                </tbody>
              </table>
            </div>
            <div className="bg-white border rounded p-4">
              <h3 className="font-semibold mb-3">用户成本分摊排名（Top 10）</h3>
              <table className="w-full text-sm">
                <thead className="text-left text-xs text-gray-500">
                  <tr><th className="py-1">用户</th><th className="py-1">Token</th><th className="py-1">成本</th></tr>
                </thead>
                <tbody>
                  {stats.by_user?.map((u: any, i: number) => (
                    <tr key={i} className="border-t">
                      <td className="py-1.5 text-xs">{u.user_id}</td>
                      <td className="py-1.5">{fmtNum(u.input_tokens + u.output_tokens)}</td>
                      <td className="py-1.5">${u.cost?.toFixed(4)}</td>
                    </tr>
                  ))}
                  {(!stats.by_user || stats.by_user.length === 0) && (
                    <tr><td colSpan={3} className="py-4 text-center text-gray-400 text-xs">暂无数据</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div className="bg-white border rounded p-4 mt-4">
            <h3 className="font-semibold mb-3">每日消耗趋势（近 {days} 天）</h3>
            {stats.daily?.length ? (
              <div className="flex items-end gap-1 h-32 overflow-x-auto">
                {stats.daily.map((d: any, i: number) => {
                  const max = Math.max(...stats.daily.map((x: any) => x.input + x.output), 1)
                  const h = Math.max(4, ((d.input + d.output) / max) * 120)
                  return (
                    <div key={i} className="flex flex-col items-center min-w-[28px]">
                      <div className="text-[10px] text-gray-500">{fmtNum(d.input + d.output)}</div>
                      <div className="w-5 bg-blue-500 rounded-t" style={{ height: h }} title={`${d.date}: ${d.input + d.output} tokens`} />
                      <div className="text-[9px] text-gray-400 mt-1">{d.date.slice(5)}</div>
                    </div>
                  )
                })}
              </div>
            ) : <div className="text-center text-gray-400 text-sm py-8">暂无趋势数据</div>}
          </div>
        </div>
      )}

      {/* ============ 预算/配额 ============ */}
      {activeTab === 'budget' && (
        <div className="grid md:grid-cols-2 gap-4">
          <div className="bg-white border rounded p-4">
            <h3 className="font-semibold mb-3">用户预算与配额</h3>
            <div className="flex gap-2 mb-4">
              <input className={inputCls} value={budgetUserId} onChange={e => setBudgetUserId(e.target.value)} placeholder="用户 ID" />
              <button className={btnSec} onClick={fetchBudget}>查询</button>
            </div>
            {budget && (
              <div className="space-y-3">
                <div>
                  <label className="text-sm text-gray-600">月度预算（USD）</label>
                  <input className={inputCls} type="number" value={budgetForm.monthly_budget ?? 10}
                    onChange={e => setBudgetForm({ ...budgetForm, monthly_budget: e.target.value })} />
                </div>
                <div>
                  <label className="text-sm text-gray-600">月度 Token 配额</label>
                  <input className={inputCls} type="number" value={budgetForm.token_quota ?? 10000000}
                    onChange={e => setBudgetForm({ ...budgetForm, token_quota: e.target.value })} />
                </div>
                <div>
                  <label className="text-sm text-gray-600">告警阈值（%）</label>
                  <input className={inputCls} type="number" value={budgetForm.alert_threshold ?? 80}
                    onChange={e => setBudgetForm({ ...budgetForm, alert_threshold: e.target.value })} />
                </div>
                <div className="flex items-center gap-4">
                  <label className="flex items-center gap-1 text-sm text-gray-600">
                    <input type="checkbox" checked={!!budgetForm.block_when_exceeded}
                      onChange={e => setBudgetForm({ ...budgetForm, block_when_exceeded: e.target.checked })} />
                    超限阻断
                  </label>
                  <label className="flex items-center gap-1 text-sm text-gray-600">
                    <input type="checkbox" checked={!!budgetForm.cascade_enabled}
                      onChange={e => setBudgetForm({ ...budgetForm, cascade_enabled: e.target.checked })} />
                    模型级联降级
                  </label>
                </div>
                <div>
                  <label className="text-sm text-gray-600">级联链（逗号分隔）</label>
                  <input className={inputCls} value={(budgetForm.cascade_chain || []).join(',')}
                    onChange={e => setBudgetForm({ ...budgetForm, cascade_chain: e.target.value.split(',').map((s: string) => s.trim()) })} />
                </div>
                <button className={btnCls} onClick={saveBudget} disabled={loading}>保存预算</button>
                <div className="border-t pt-3 text-sm space-y-1">
                  <div>当前用量：{fmtNum(budget.month_tokens)} / {fmtNum(budget.quota)}（{budget.usage_pct}%）</div>
                  <div>当前成本：${budget.month_cost} / ${budget.monthly_budget}（{budget.cost_pct}%）</div>
                  <div className={`font-medium ${budget.blocked ? 'text-red-600' : 'text-green-600'}`}>
                    状态：{budget.blocked ? '已阻断（超限）' : '正常'}
                  </div>
                </div>
              </div>
            )}
          </div>
          <div className="bg-white border rounded p-4">
            <h3 className="font-semibold mb-3">预算/配额告警</h3>
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-gray-500">
                <tr><th className="py-1">时间</th><th className="py-1">类型</th><th className="py-1">级别</th><th className="py-1">消息</th><th className="py-1">状态</th></tr>
              </thead>
              <tbody>
                {alerts.map(a => (
                  <tr key={a.id} className="border-t">
                    <td className="py-1.5 text-xs">{a.created_at?.slice(0, 10)}</td>
                    <td className="py-1.5 text-xs">{a.alert_type}</td>
                    <td className="py-1.5"><span className={`px-1.5 py-0.5 rounded text-xs ${a.severity === 'critical' ? 'bg-red-100 text-red-700' : 'bg-yellow-100 text-yellow-700'}`}>{a.severity}</span></td>
                    <td className="py-1.5 text-xs">{a.message}</td>
                    <td className="py-1.5">
                      <select className="text-xs border rounded px-1 py-0.5" value={a.status}
                        onChange={e => { updateTokenAlert(a.id, e.target.value); fetchBudget() }}>
                        <option value="open">未处理</option>
                        <option value="acknowledged">已确认</option>
                        <option value="resolved">已解决</option>
                      </select>
                    </td>
                  </tr>
                ))}
                {alerts.length === 0 && <tr><td colSpan={5} className="py-6 text-center text-gray-400 text-xs">暂无告警</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ============ 优化策略 ============ */}
      {activeTab === 'optimize' && (
        <div className="grid md:grid-cols-2 gap-4">
          <div className="bg-white border rounded p-4">
            <h3 className="font-semibold mb-3">模型选择建议</h3>
            <div className="flex items-center gap-2 mb-3">
              <span className="text-sm text-gray-600">任务类型</span>
              <select className={inputCls} style={{ width: 160 }} value={taskType} onChange={e => setTaskType(e.target.value)}>
                {TASK_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
              <button className={btnSec} onClick={fetchOptimize}>查询</button>
            </div>
            {suggestion && (
              <div className="bg-blue-50 border border-blue-200 rounded p-3">
                <div className="font-bold text-blue-800">推荐：{suggestion.suggested_model}</div>
                <div className="text-sm text-blue-700 mt-1">性价比评分：{suggestion.score}/100</div>
                <div className="text-sm text-blue-600 mt-1">{suggestion.reason}</div>
                <div className="mt-2 text-xs text-blue-500">
                  备选：{suggestion.alternatives?.map((a: any) => `${a.model}(${a.score})`).join(' · ')}
                </div>
              </div>
            )}
            <div className="mt-4 border-t pt-3">
              <h4 className="font-semibold text-sm mb-2">上下文裁剪（Prompt 压缩）</h4>
              <textarea className="border border-gray-300 rounded px-2 py-1 text-sm w-full h-20" value={sampleText}
                onChange={e => setSampleText(e.target.value)} placeholder="输入要优化的文本…" />
              <button className={`${btnCls} mt-2`} onClick={doOptimize} disabled={loading}>执行裁剪</button>
              {optResult && (
                <div className="mt-3 bg-gray-50 rounded p-3 text-xs text-gray-600">
                  <div>原始 Token：{optResult.original_tokens} → 保留：{optResult.kept_tokens}</div>
                  <div>节省：{optResult.compressed_tokens} Token（压缩率 {optResult.ratio}%）</div>
                </div>
              )}
            </div>
          </div>
          <div className="space-y-4">
            <div className="bg-white border rounded p-4">
              <h3 className="font-semibold mb-3">模型级联计划（{taskType}）</h3>
              {cascadePlan && (
                <div className="text-sm space-y-2">
                  <div>主模型：<span className="font-mono font-bold">{cascadePlan.primary_model}</span></div>
                  <div>降级链：<span className="font-mono">{cascadePlan.fallback_chain?.join(' → ')}</span></div>
                  <div>最大输入：{fmtNum(cascadePlan.max_input_tokens)} tokens</div>
                  <div>状态：{cascadePlan.enabled ? <span className="text-green-600">已启用</span> : <span className="text-gray-400">已停用</span>}</div>
                  <button className={`${btnSec} mt-2`} onClick={() => saveCascade(taskType)} disabled={loading}>保存级联规则</button>
                </div>
              )}
            </div>
            <div className="bg-white border rounded p-4">
              <h3 className="font-semibold mb-3">全部级联规则</h3>
              <table className="w-full text-sm">
                <thead className="text-left text-xs text-gray-500">
                  <tr><th className="py-1">任务</th><th className="py-1">主模型</th><th className="py-1">降级链</th><th className="py-1">状态</th></tr>
                </thead>
                <tbody>
                  {cascadeRules.map((r: any, i: number) => (
                    <tr key={i} className="border-t">
                      <td className="py-1.5 text-xs">{r.task_type}</td>
                      <td className="py-1.5 font-mono text-xs">{r.primary_model}</td>
                      <td className="py-1.5 font-mono text-xs">{r.fallback_chain?.join('→')}</td>
                      <td className="py-1.5">{r.enabled ? '✅' : '❌'}</td>
                    </tr>
                  ))}
                  {cascadeRules.length === 0 && <tr><td colSpan={4} className="py-4 text-center text-gray-400 text-xs">暂无规则</td></tr>}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ============ 效果评估 ============ */}
      {activeTab === 'effect' && effect && (
        <div>
          <div className="flex items-center gap-3 mb-4">
            <span className="text-sm text-gray-600">评估周期</span>
            <select className={inputCls} style={{ width: 140 }} value={days} onChange={e => setDays(Number(e.target.value))}>
              <option value={7}>近 7 天</option>
              <option value={30}>近 30 天</option>
              <option value={90}>近 90 天</option>
            </select>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <div className="bg-white border rounded p-4">
              <div className="text-3xl font-bold text-blue-600">{effect.cache_hit_rate}%</div>
              <div className="text-xs text-gray-500 mt-1">缓存命中率</div>
            </div>
            <div className="bg-white border rounded p-4">
              <div className="text-3xl font-bold text-green-600">{effect.compression_rate}%</div>
              <div className="text-xs text-gray-500 mt-1">上下文压缩率</div>
            </div>
            <div className="bg-white border rounded p-4">
              <div className="text-3xl font-bold text-orange-600">${effect.cost_saved?.toFixed(4)}</div>
              <div className="text-xs text-gray-500 mt-1">节省成本（估算）</div>
            </div>
          </div>
          <div className="bg-white border rounded p-4 mt-4">
            <h3 className="font-semibold mb-3">详细数据（近 {effect.days} 天）</h3>
            <div className="grid md:grid-cols-3 gap-4 text-sm">
              <div className="space-y-1">
                <div className="text-gray-500">总输入 Token</div><div className="font-bold">{fmtNum(effect.total_input)}</div>
                <div className="text-gray-500">总输出 Token</div><div className="font-bold">{fmtNum(effect.total_output)}</div>
              </div>
              <div className="space-y-1">
                <div className="text-gray-500">缓存命中 Token</div><div className="font-bold">{fmtNum(effect.cached_tokens)}</div>
                <div className="text-gray-500">压缩节省 Token</div><div className="font-bold">{fmtNum(effect.compressed_tokens)}</div>
              </div>
              <div className="space-y-1">
                <div className="text-gray-500">实际总成本</div><div className="font-bold">${effect.total_cost?.toFixed(4)}</div>
                <div className="text-gray-500">级联降级节省</div><div className="font-bold">${effect.cascade_saved_cost?.toFixed(4)}</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ============ 用量明细 ============ */}
      {activeTab === 'usage' && (
        <div>
          <div className="bg-white border rounded overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-gray-600 text-left">
                <tr>
                  <th className="px-3 py-2">时间</th>
                  <th className="px-3 py-2">用户</th>
                  <th className="px-3 py-2">模型</th>
                  <th className="px-3 py-2">输入</th>
                  <th className="px-3 py-2">输出</th>
                  <th className="px-3 py-2">缓存</th>
                  <th className="px-3 py-2">压缩</th>
                  <th className="px-3 py-2">成本</th>
                </tr>
              </thead>
              <tbody>
                {usageItems.map((u: any) => (
                  <tr key={u.id} className="border-t hover:bg-gray-50">
                    <td className="px-3 py-2 text-xs whitespace-nowrap">{u.created_at?.slice(0, 19).replace('T', ' ')}</td>
                    <td className="px-3 py-2 text-xs">{u.user_id}</td>
                    <td className="px-3 py-2 font-mono text-xs">{u.model_name}</td>
                    <td className="px-3 py-2">{fmtNum(u.input_tokens)}</td>
                    <td className="px-3 py-2">{fmtNum(u.output_tokens)}</td>
                    <td className="px-3 py-2 text-xs">{fmtNum(u.cached_tokens)}</td>
                    <td className="px-3 py-2 text-xs">{fmtNum(u.compressed_tokens)}</td>
                    <td className="px-3 py-2 text-xs">${u.cost?.toFixed(6)}</td>
                  </tr>
                ))}
                {usageItems.length === 0 && <tr><td colSpan={8} className="px-3 py-8 text-center text-gray-400">暂无用量记录</td></tr>}
              </tbody>
            </table>
            <div className="flex items-center justify-between px-3 py-2 border-t bg-gray-50 text-sm">
              <span>共 {usageTotal} 条</span>
              <div className="flex gap-2">
                <button className={btnSec} disabled={usagePage <= 1} onClick={() => setUsagePage(usagePage - 1)}>上一页</button>
                <span className="py-1">第 {usagePage} 页</span>
                <button className={btnSec} disabled={usagePage * 20 >= usageTotal} onClick={() => setUsagePage(usagePage + 1)}>下一页</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
