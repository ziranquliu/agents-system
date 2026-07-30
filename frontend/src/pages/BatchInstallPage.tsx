import React, { useEffect, useState, useCallback } from 'react'
import {
  batchPrecheck, createBatchInstall, executeBatch,
  listBatchQueues, getBatchQueueItems, getBatchReport,
  BatchPrecheckResult, BatchInstallQueue, BatchInstallItem,
} from '../api/batchInstall'
import apiFetch from '../api/client'
import { useToast } from '../components/ui'

const BatchInstallPage: React.FC = () => {
  const toast = useToast()

  // 标签页
  const [tab, setTab] = useState<'new' | 'history' | 'detail' | 'report'>('new')

  // 步骤
  const [step, setStep] = useState<'select' | 'precheck' | 'confirm' | 'running'>('select')

  // 可供选择的 Skills 和 Agents
  const [skills, setSkills] = useState<any[]>([])
  const [agents, setAgents] = useState<any[]>([])
  const [loadingOptions, setLoadingOptions] = useState(false)

  // 选中
  const [selectedSkillIds, setSelectedSkillIds] = useState<string[]>([])
  const [selectedAgentIds, setSelectedAgentIds] = useState<string[]>([])

  // 预检结果
  const [precheck, setPrecheck] = useState<BatchPrecheckResult | null>(null)
  const [prechecking, setPrechecking] = useState(false)

  // 队列
  const [currentQueue, setCurrentQueue] = useState<BatchInstallQueue | null>(null)
  const [queueItems, setQueueItems] = useState<BatchInstallItem[]>([])
  const [executing, setExecuting] = useState(false)

  // 历史
  const [queues, setQueues] = useState<BatchInstallQueue[]>([])
  const [loadingQueues, setLoadingQueues] = useState(false)

  // 报告
  const [report, setReport] = useState<Record<string, unknown> | null>(null)
  const [reportId, setReportId] = useState<string | null>(null)
  const [loadingReport, setLoadingReport] = useState(false)

  const loadOptions = useCallback(async () => {
    setLoadingOptions(true)
    try {
      const [skillsResp, agentsResp] = await Promise.all([
        apiFetch('/api/v1/skills', { method: 'GET' }),
        apiFetch('/api/v1/agents', { method: 'GET' }),
      ])
      const skillsData = skillsResp.data?.data || skillsResp.data || []
      const agentsData = agentsResp.data?.data || agentsResp.data || []
      setSkills(Array.isArray(skillsData) ? skillsData : [])
      setAgents(Array.isArray(agentsData) ? agentsData : [])
    } catch {
      toast.error('加载选项失败')
    } finally {
      setLoadingOptions(false)
    }
  }, [toast])

  useEffect(() => { loadOptions() }, [])

  const handlePrecheck = async () => {
    if (selectedSkillIds.length === 0 || selectedAgentIds.length === 0) {
      toast.error('请至少选择一个 Skill 和一个 Agent')
      return
    }
    setPrechecking(true)
    try {
      const result = await batchPrecheck(selectedSkillIds, selectedAgentIds)
      setPrecheck(result)
      setStep('precheck')
    } catch {
      toast.error('预检失败')
    } finally {
      setPrechecking(false)
    }
  }

  const handleInstall = async (force = false) => {
    if (precheck && precheck.status === 'blocked' && !force) {
      toast.error('存在阻塞性依赖，无法安装。如需忽略请确认强制安装')
      return
    }
    setExecuting(true)
    try {
      const queue = await createBatchInstall(selectedSkillIds, selectedAgentIds, 'install')
      setCurrentQueue(queue)
      setStep('running')

      // 自动执行
      const result = await executeBatch(queue.id)
      setCurrentQueue(result)

      const itemsResp = await getBatchQueueItems(queue.id)
      setQueueItems(itemsResp.data || [])

      toast.success(`安装完成: ${result.success_count} 成功, ${result.fail_count} 失败`)
    } catch {
      toast.error('安装失败')
    } finally {
      setExecuting(false)
    }
  }

  const loadQueues = useCallback(async () => {
    setLoadingQueues(true)
    try {
      const result = await listBatchQueues()
      setQueues(result.data || [])
    } catch {
      toast.error('加载历史失败')
    } finally {
      setLoadingQueues(false)
    }
  }, [toast])

  useEffect(() => {
    if (tab === 'history') loadQueues()
  }, [tab])

  const loadReport = async (queueId: string) => {
    setReportId(queueId)
    setTab('report')
    setLoadingReport(true)
    try {
      const result = await getBatchReport(queueId)
      setReport(result)
    } catch {
      toast.error('加载报告失败')
    } finally {
      setLoadingReport(false)
    }
  }

  const toggleSkill = (id: string) => {
    setSelectedSkillIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    )
  }

  const toggleAgent = (id: string) => {
    setSelectedAgentIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    )
  }

  const resetSelection = () => {
    setSelectedSkillIds([])
    setSelectedAgentIds([])
    setPrecheck(null)
    setCurrentQueue(null)
    setQueueItems([])
    setStep('select')
  }

  const renderStatusBadge = (status: string) => {
    const m: Record<string, [string, string]> = {
      passed: ['✅ 通过', 'text-green-600 bg-green-50'],
      warning: ['⚠️ 警告', 'text-yellow-600 bg-yellow-50'],
      blocked: ['🚫 阻塞', 'text-red-600 bg-red-50'],
      success: ['✅ 成功', 'text-green-600 bg-green-50'],
      failed: ['❌ 失败', 'text-red-600 bg-red-50'],
      skipped: ['⏭️ 跳过', 'text-gray-500 bg-gray-50'],
      running: ['🔄 执行中', 'text-blue-600 bg-blue-50'],
      pending: ['⏳ 等待中', 'text-yellow-600 bg-yellow-50'],
      completed: ['✅ 完成', 'text-green-600 bg-green-50'],
      cancelled: ['❌ 已取消', 'text-gray-500 bg-gray-50'],
    }
    const [label, cls] = m[status] || [status, 'text-gray-500']
    return <span className={`px-2 py-0.5 rounded text-xs font-medium ${cls}`}>{label}</span>
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold flex items-center gap-2">📦 批量 Skill 安装</h1>
        <p className="text-gray-500 mt-1">多选安装 · 依赖预检 · 安装队列 · 报告</p>
      </div>

      {/* 标签页 */}
      <div className="flex gap-1 mb-6 border-b">
        {[
          { key: 'new', label: '🆕 新建批量安装' },
          { key: 'history', label: '📋 安装历史' },
          { key: 'report', label: '📄 安装报告' },
        ].map(t => (
          <button key={t.key} onClick={() => { setTab(t.key as any); if (t.key === 'new') resetSelection() }}
            className={`px-4 py-2 text-sm border-b-2 transition-colors ${tab === t.key ? 'border-blue-500 text-blue-600 font-medium' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* ==================== 新建 ==================== */}
      {tab === 'new' && (
        <div className="space-y-4">
          {/* 步骤指示器 */}
          <div className="flex items-center gap-2 text-sm mb-4">
            {[
              { key: 'select', label: '选择资源' },
              { key: 'precheck', label: '依赖预检' },
              { key: 'confirm', label: '确认安装' },
              { key: 'running', label: '执行结果' },
            ].map((s, i) => (
              <React.Fragment key={s.key}>
                <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium
                  ${step === s.key ? 'bg-blue-100 text-blue-700 ring-2 ring-blue-300'
                    : ['precheck', 'confirm', 'running'].includes(step) && ['precheck', 'confirm', 'running'].indexOf(step) >= i
                      ? 'bg-green-100 text-green-600' : 'bg-gray-100 text-gray-400'}`}>
                  {['precheck', 'confirm', 'running'].includes(step) && ['precheck', 'confirm', 'running'].indexOf(step) >= i ? '✓' : i + 1}
                  <span>{s.label}</span>
                </div>
                {i < 3 && <div className="w-6 h-px bg-gray-300" />}
              </React.Fragment>
            ))}
          </div>

          {/* 步骤1: 选择 */}
          {step === 'select' && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
                <div className="px-4 py-3 border-b bg-gray-50 flex items-center justify-between">
                  <span className="font-semibold text-sm">选择 Skill ({selectedSkillIds.length})</span>
                  <button onClick={() => setSelectedSkillIds(skills.map((s: any) => s.id))}
                    className="text-xs text-blue-600 hover:underline">全选</button>
                </div>
                {loadingOptions ? (
                  <div className="flex justify-center py-8"><div className="animate-spin w-5 h-5 border-2 border-blue-600 border-t-transparent rounded-full" /></div>
                ) : (
                  <div className="max-h-80 overflow-y-auto divide-y">
                    {skills.map((s: any) => (
                      <label key={s.id} className="flex items-center px-4 py-2.5 hover:bg-gray-50 cursor-pointer text-sm">
                        <input type="checkbox" checked={selectedSkillIds.includes(s.id)} onChange={() => toggleSkill(s.id)} className="mr-3" />
                        <div>
                          <span className="font-medium">{s.name || s.title || '未命名'}</span>
                          <span className="text-gray-400 ml-2">{s.type || s.skill_type || ''}</span>
                        </div>
                      </label>
                    ))}
                    {skills.length === 0 && <div className="text-center py-8 text-gray-400 text-sm">暂无可用 Skill</div>}
                  </div>
                )}
              </div>

              <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
                <div className="px-4 py-3 border-b bg-gray-50 flex items-center justify-between">
                  <span className="font-semibold text-sm">选择目标智能体 ({selectedAgentIds.length})</span>
                  <button onClick={() => setSelectedAgentIds(agents.map((a: any) => a.id))}
                    className="text-xs text-blue-600 hover:underline">全选</button>
                </div>
                {loadingOptions ? (
                  <div className="flex justify-center py-8"><div className="animate-spin w-5 h-5 border-2 border-blue-600 border-t-transparent rounded-full" /></div>
                ) : (
                  <div className="max-h-80 overflow-y-auto divide-y">
                    {agents.map((a: any) => (
                      <label key={a.id} className="flex items-center px-4 py-2.5 hover:bg-gray-50 cursor-pointer text-sm">
                        <input type="checkbox" checked={selectedAgentIds.includes(a.id)} onChange={() => toggleAgent(a.id)} className="mr-3" />
                        <div>
                          <span className="font-medium">{a.name || a.id}</span>
                          <span className="text-gray-400 ml-2">{a.agent_type || ''}</span>
                        </div>
                      </label>
                    ))}
                    {agents.length === 0 && <div className="text-center py-8 text-gray-400 text-sm">暂无可用智能体</div>}
                  </div>
                )}
              </div>
            </div>
          )}

          <div className="flex gap-3 justify-end">
            {step === 'select' && (
              <button onClick={handlePrecheck} disabled={selectedSkillIds.length === 0 || selectedAgentIds.length === 0 || prechecking}
                className="px-5 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50">
                {prechecking ? '预检中...' : '依赖预检 →'}
              </button>
            )}

            {/* 预检结果 */}
            {step === 'precheck' && precheck && (
              <div className="w-full">
                <div className={`rounded-xl p-4 mb-4 ${precheck.status === 'passed' ? 'bg-green-50 border border-green-200'
                  : precheck.status === 'warning' ? 'bg-yellow-50 border border-yellow-200'
                    : 'bg-red-50 border border-red-200'}`}>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-lg">{precheck.status === 'passed' ? '✅' : precheck.status === 'warning' ? '⚠️' : '🚫'}</span>
                    <span className="font-semibold">{precheck.status === 'passed' ? '预检通过'
                      : precheck.status === 'warning' ? '预检通过（有警告）' : '预检未通过'}</span>
                  </div>
                  <p className="text-sm">{precheck.summary}</p>
                  <div className="flex gap-3 mt-2 text-xs text-gray-500">
                    <span>总计 {precheck.total} 项</span>
                    <span className="text-green-600">{precheck.passed_count} 通过</span>
                    <span className="text-yellow-600">{precheck.warning_count} 警告</span>
                    <span className="text-red-600">{precheck.blocked_count} 阻塞</span>
                  </div>
                </div>

                {/* 依赖详情 */}
                <div className="bg-white border border-gray-200 rounded-xl max-h-60 overflow-y-auto">
                  <div className="px-4 py-2 border-b bg-gray-50 text-xs font-medium text-gray-500">依赖检查详情</div>
                  {precheck.items.map((item, i) => (
                    <div key={i} className="px-4 py-2 border-b last:border-0 text-sm flex items-center justify-between">
                      <div>
                        <span className="font-medium">{item.skill_name}</span>
                        <span className="text-gray-400 mx-1">→</span>
                        <code className="text-xs bg-gray-100 px-1">{item.agent_id}</code>
                      </div>
                      <div className="flex items-center gap-2">
                        {renderStatusBadge(item.dep_check_status)}
                        {Array.isArray(item.dep_check_detail) && item.dep_check_detail.length > 0 && (
                          <details className="text-xs text-gray-500">
                            <summary className="cursor-pointer hover:text-blue-600">详情</summary>
                            <pre className="mt-1 p-2 bg-gray-50 rounded max-w-md overflow-x-auto">
                              {JSON.stringify(item.dep_check_detail, null, 2)}
                            </pre>
                          </details>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="flex gap-3 mt-4 justify-end">
                  <button onClick={() => setStep('select')} className="px-4 py-2 border rounded-lg text-sm">返回选择</button>
                  <button onClick={() => handleInstall(false)}
                    disabled={precheck.status === 'blocked' || executing}
                    className="px-5 py-2 bg-green-600 text-white rounded-lg text-sm hover:bg-green-700 disabled:opacity-50">
                    确认安装
                  </button>
                  {precheck.status === 'blocked' && (
                    <button onClick={() => handleInstall(true)} disabled={executing}
                      className="px-5 py-2 bg-orange-500 text-white rounded-lg text-sm hover:bg-orange-600 disabled:opacity-50">
                      强制安装（忽略阻塞）
                    </button>
                  )}
                </div>
              </div>
            )}

            {/* 执行结果 */}
            {step === 'running' && (
              <div className="w-full space-y-4">
                {currentQueue && (
                  <div className={`rounded-xl p-4 ${currentQueue.status === 'completed' ? 'bg-green-50 border border-green-200' : 'bg-blue-50 border border-blue-200'}`}>
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-lg">{currentQueue.status === 'completed' ? '✅' : '🔄'}</span>
                      <span className="font-semibold">队列 {currentQueue.id.slice(0, 8)}... — {renderStatusBadge(currentQueue.status)}</span>
                    </div>
                    <div className="flex gap-4 text-sm">
                      <span>总 {currentQueue.total_items}</span>
                      <span className="text-green-600">✓ {currentQueue.success_count}</span>
                      <span className="text-red-600">✗ {currentQueue.fail_count}</span>
                      <span className="text-yellow-600">⚠ {currentQueue.warn_count}</span>
                    </div>
                  </div>
                )}

                {/* 详情列表 */}
                {queueItems.length > 0 && (
                  <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
                    <div className="px-4 py-2 border-b bg-gray-50 text-xs font-medium text-gray-500">安装明细</div>
                    <div className="divide-y max-h-80 overflow-y-auto">
                      {queueItems.map(item => (
                        <div key={item.id} className="px-4 py-2.5 flex items-center justify-between text-sm">
                          <div>
                            <span className="font-medium">{item.skill_name || item.skill_id.slice(0, 8)}</span>
                            <span className="text-gray-400 mx-1">→</span>
                            <code className="text-xs bg-gray-100 px-1">{item.agent_id.slice(0, 12)}...</code>
                          </div>
                          <div className="flex items-center gap-2">
                            {renderStatusBadge(item.status)}
                            {item.error_message && <span className="text-xs text-red-500" title={item.error_message}>⚠</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="flex gap-3 justify-end">
                  <button onClick={resetSelection} className="px-4 py-2 border rounded-lg text-sm">新建安装</button>
                  {currentQueue && (
                    <button onClick={() => loadReport(currentQueue.id)}
                      className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm">查看报告</button>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ==================== 历史 ==================== */}
      {tab === 'history' && (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="px-5 py-3 border-b bg-gray-50 font-semibold text-sm">批量安装历史</div>
          {loadingQueues ? (
            <div className="flex justify-center py-12"><div className="animate-spin w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full" /></div>
          ) : queues.length === 0 ? (
            <div className="text-center py-12 text-gray-400 text-sm">暂无安装记录</div>
          ) : (
            <div className="divide-y">
              {queues.map(q => (
                <div key={q.id} className="px-5 py-3 flex items-center justify-between text-sm hover:bg-gray-50">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs">{q.id.slice(0, 12)}...</span>
                      {renderStatusBadge(q.status)}
                      {renderStatusBadge(q.precheck_status || '')}
                    </div>
                    <div className="flex gap-3 mt-1 text-xs text-gray-500">
                      <span>{q.operation}</span>
                      <span>总 {q.total_items}</span>
                      <span className="text-green-600">✓ {q.success_count}</span>
                      <span className="text-red-600">✗ {q.fail_count}</span>
                      <span>创建于 {q.created_at ? new Date(q.created_at).toLocaleString() : '-'}</span>
                    </div>
                  </div>
                  <button onClick={() => loadReport(q.id)}
                    className="px-3 py-1 text-xs border rounded hover:bg-gray-50">报告</button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ==================== 报告 ==================== */}
      {tab === 'report' && (
        <div className="bg-white border border-gray-200 rounded-xl">
          <div className="px-5 py-3 border-b bg-gray-50 flex items-center justify-between">
            <span className="font-semibold text-sm">安装报告 {reportId ? `#${reportId.slice(0, 8)}` : ''}</span>
            {report && <button onClick={() => {
              const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
              const url = URL.createObjectURL(blob)
              const a = document.createElement('a')
              a.href = url; a.download = `install-report-${reportId?.slice(0, 8)}.json`; a.click()
              URL.revokeObjectURL(url)
            }} className="px-3 py-1 text-xs border rounded hover:bg-gray-50">导出报告</button>}
          </div>
          {loadingReport ? (
            <div className="flex justify-center py-12"><div className="animate-spin w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full" /></div>
          ) : report ? (
            <div className="p-5">
              <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-4">
                {[
                  { label: '操作', value: (report as any).operation, color: 'bg-blue-50 text-blue-700' },
                  { label: '状态', value: (report as any).status, color: 'bg-gray-50 text-gray-700' },
                  { label: '总项', value: (report as any).total, color: 'bg-blue-50 text-blue-700' },
                  { label: '成功', value: (report as any).success, color: 'bg-green-50 text-green-700' },
                  { label: '失败', value: (report as any).failed, color: 'bg-red-50 text-red-700' },
                ].map(c => (
                  <div key={c.label} className={`rounded-xl p-3 ${c.color}`}>
                    <div className="text-xs opacity-70">{c.label}</div>
                    <div className="text-lg font-bold mt-0.5">{c.value === null || c.value === undefined ? '-' : String(c.value)}</div>
                  </div>
                ))}
              </div>

              {report.precheck_summary && (
                <div className="mb-4 text-sm text-gray-600 bg-gray-50 rounded-lg p-3">
                  <strong>预检:</strong> {String(report.precheck_summary)}
                </div>
              )}

              {(report as any).items && Array.isArray((report as any).items) && (
                <div className="border border-gray-200 rounded-lg overflow-hidden">
                  <div className="px-4 py-2 bg-gray-50 text-xs font-medium text-gray-500 border-b">安装明细</div>
                  <div className="divide-y max-h-80 overflow-y-auto">
                    {(report as any).items.map((item: any, i: number) => (
                      <div key={i} className="px-4 py-2 flex items-center justify-between text-sm">
                        <div>
                          <span className="font-medium">{item.skill_name || item.skill_id?.slice(0, 8)}</span>
                          <span className="text-gray-400 mx-1">→</span>
                          <code className="text-xs">{item.agent_id?.slice(0, 12)}...</code>
                        </div>
                        <div className="flex items-center gap-2">
                          {renderStatusBadge(item.status)}
                          {item.error_message && <span className="text-xs text-red-500 max-w-[200px] truncate" title={item.error_message}>{item.error_message}</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <pre className="mt-4 bg-gray-50 rounded-lg p-4 text-xs text-gray-500 max-h-60 overflow-auto">
                {JSON.stringify(report, null, 2)}
              </pre>
            </div>
          ) : (
            <div className="text-center py-12 text-gray-400 text-sm">请从安装历史中选择一个队列查看报告</div>
          )}
        </div>
      )}
    </div>
  )
}

export default BatchInstallPage
