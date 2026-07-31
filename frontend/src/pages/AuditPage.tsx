import { useState, useEffect, useCallback } from 'react'
import {
  listAuditLogs, getAuditStats, verifyAuditChain, verifyAuditRecord,
  exportAuditCsv, exportAuditSiem,
  scanAnomalies, listAnomalies, updateAnomalyStatus,
  listAuditRules, createAuditRule, updateAuditRule, deleteAuditRule,
  listAuditArchives, runAuditArchive, runAuditRetention,
  getAuditConfig, updateAuditConfig, createAuditLog,
} from '../api/audit'

const CATEGORY_COLORS: Record<string, string> = {
  user: 'bg-blue-100 text-blue-700',
  agent: 'bg-purple-100 text-purple-700',
  system: 'bg-teal-100 text-teal-700',
  security: 'bg-orange-100 text-orange-700',
}

const RESULT_COLORS: Record<string, string> = {
  success: 'bg-green-100 text-green-700',
  failure: 'bg-red-100 text-red-700',
  denied: 'bg-yellow-100 text-yellow-700',
}

const SEVERITY_COLORS: Record<string, string> = {
  low: 'bg-gray-100 text-gray-600',
  medium: 'bg-yellow-100 text-yellow-700',
  high: 'bg-orange-100 text-orange-700',
  critical: 'bg-red-100 text-red-700',
}

const TABS = [
  { key: 'logs', label: '审计日志' },
  { key: 'verify', label: '防篡改校验' },
  { key: 'anomalies', label: '异常检测' },
  { key: 'rules', label: '检测规则' },
  { key: 'export', label: '导出/SIEM' },
  { key: 'config', label: '配置/归档' },
]

interface Row { id: string; [key: string]: any }

function fmt(ts?: string) {
  if (!ts) return '-'
  return ts.replace('T', ' ').slice(0, 19)
}

function shorten(hash?: string) {
  if (!hash) return '-'
  return hash.slice(0, 12) + '…'
}

export default function AuditPage() {
  const [activeTab, setActiveTab] = useState('logs')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  // ========== 日志查询 ==========
  const [logs, setLogs] = useState<Row[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [stats, setStats] = useState<any>(null)
  const [filters, setFilters] = useState<any>({
    operator_id: '', action_type: '', category: '', target_id: '', result: '',
  })

  const fetchLogs = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const params: any = { page, page_size: pageSize }
      if (filters.operator_id) params.operator_id = filters.operator_id
      if (filters.action_type) params.action_type = filters.action_type
      if (filters.category) params.category = filters.category
      if (filters.target_id) params.target_id = filters.target_id
      if (filters.result) params.result = filters.result
      const res = await listAuditLogs(params)
      setLogs(res.data.items || [])
      setTotal(res.data.total || 0)
      const st = await getAuditStats()
      setStats(st.data)
    } catch (e: any) {
      setError(e?.response?.data?.detail || '加载审计日志失败')
    } finally { setLoading(false) }
  }, [page, pageSize, filters])

  useEffect(() => { fetchLogs() }, [fetchLogs])

  // ========== 防篡改校验 ==========
  const [verifyResult, setVerifyResult] = useState<any>(null)
  const [verifyRecordId, setVerifyRecordId] = useState('')
  const [singleVerify, setSingleVerify] = useState<any>(null)

  const doVerifyChain = async () => {
    setLoading(true); setError(''); setVerifyResult(null)
    try {
      const res = await verifyAuditChain()
      setVerifyResult(res.data)
    } catch (e: any) { setError(e?.response?.data?.detail || '校验失败') } finally { setLoading(false) }
  }

  const doVerifyRecord = async () => {
    if (!verifyRecordId) return
    setLoading(true); setError(''); setSingleVerify(null)
    try {
      const res = await verifyAuditRecord(verifyRecordId)
      setSingleVerify(res.data)
    } catch (e: any) { setError(e?.response?.data?.detail || '校验失败') } finally { setLoading(false) }
  }

  // ========== 异常检测 ==========
  const [anomalies, setAnomalies] = useState<Row[]>([])
  const [anomalyTotal, setAnomalyTotal] = useState(0)
  const [anomalyFilter, setAnomalyFilter] = useState({ severity: '', status: '' })
  const [scanning, setScanning] = useState(false)

  const fetchAnomalies = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const params: any = { page: 1, page_size: 50 }
      if (anomalyFilter.severity) params.severity = anomalyFilter.severity
      if (anomalyFilter.status) params.status = anomalyFilter.status
      const res = await listAnomalies(params)
      setAnomalies(res.data.items || [])
      setAnomalyTotal(res.data.total || 0)
    } catch (e: any) { setError(e?.response?.data?.detail || '加载异常告警失败') } finally { setLoading(false) }
  }, [anomalyFilter])

  useEffect(() => { if (activeTab === 'anomalies') fetchAnomalies() }, [activeTab, fetchAnomalies])

  const doScan = async () => {
    setScanning(true); setError(''); setSuccess('')
    try {
      const res = await scanAnomalies()
      setSuccess(`检测完成：产生 ${res.data?.alerts_created ?? 0} 条告警`)
      fetchAnomalies()
    } catch (e: any) { setError(e?.response?.data?.detail || '检测失败') } finally { setScanning(false) }
  }

  const doUpdateAnomaly = async (id: string, status: string) => {
    try {
      await updateAnomalyStatus(id, status)
      fetchAnomalies()
    } catch (e: any) { setError(e?.response?.data?.detail || '更新失败') }
  }

  // ========== 检测规则 ==========
  const [rules, setRules] = useState<Row[]>([])
  const [showRuleForm, setShowRuleForm] = useState(false)
  const [ruleForm, setRuleForm] = useState<any>({ rule_name: '', rule_type: 'off_hours', severity: 'medium', enabled: true, params: '{}' })

  const fetchRules = useCallback(async () => {
    try {
      const res = await listAuditRules()
      setRules(res.data || [])
    } catch (e: any) { setError(e?.response?.data?.detail || '加载规则失败') }
  }, [])
  useEffect(() => { if (activeTab === 'rules') fetchRules() }, [activeTab, fetchRules])

  const saveRule = async () => {
    setLoading(true); setError('')
    try {
      let params: any = {}
      try { params = JSON.parse(ruleForm.params || '{}') } catch { params = {} }
      await createAuditRule({ ...ruleForm, params })
      setShowRuleForm(false)
      setRuleForm({ rule_name: '', rule_type: 'off_hours', severity: 'medium', enabled: true, params: '{}' })
      setSuccess('规则创建成功')
      fetchRules()
    } catch (e: any) { setError(e?.response?.data?.detail || '创建失败') } finally { setLoading(false) }
  }

  const toggleRule = async (rule: Row) => {
    try {
      let params: any = {}
      try { params = JSON.parse(rule.params || '{}') } catch { params = {} }
      await updateAuditRule(rule.id, { enabled: !rule.enabled, params })
      fetchRules()
    } catch (e: any) { setError(e?.response?.data?.detail || '更新失败') }
  }

  const removeRule = async (id: string) => {
    if (!window.confirm('确定删除该规则？')) return
    try {
      await deleteAuditRule(id)
      fetchRules()
      setSuccess('规则已删除')
    } catch (e: any) { setError(e?.response?.data?.detail || '删除失败') }
  }

  // ========== 导出/SIEM ==========
  const doExportCsv = async () => {
    setLoading(true); setError('')
    try {
      const params: any = {}
      if (filters.operator_id) params.operator_id = filters.operator_id
      if (filters.action_type) params.action_type = filters.action_type
      if (filters.category) params.category = filters.category
      if (filters.result) params.result = filters.result
      const res = await exportAuditCsv(params)
      const blob = new Blob([res.data], { type: 'text/csv' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `audit_${new Date().toISOString().slice(0, 10)}.csv`
      a.click()
      URL.revokeObjectURL(url)
      setSuccess('CSV 已导出')
    } catch (e: any) { setError(e?.response?.data?.detail || '导出失败') } finally { setLoading(false) }
  }

  const [siemLines, setSiemLines] = useState<string[]>([])
  const [siemMinutes, setSiemMinutes] = useState(60)
  const doExportSiem = async () => {
    setLoading(true); setError('')
    try {
      const res = await exportAuditSiem(siemMinutes)
      setSiemLines((res.data || '').split('\n').filter(Boolean))
    } catch (e: any) { setError(e?.response?.data?.detail || 'SIEM 导出失败') } finally { setLoading(false) }
  }

  // ========== 配置/归档 ==========
  const [archives, setArchives] = useState<Row[]>([])
  const [configForm, setConfigForm] = useState<any>({})

  const fetchConfig = useCallback(async () => {
    try {
      const res = await getAuditConfig()
      setConfigForm(res.data)
    } catch (e: any) { setError(e?.response?.data?.detail || '加载配置失败') }
  }, [])
  useEffect(() => { if (activeTab === 'config') { fetchConfig(); fetchArchives() } }, [activeTab, fetchConfig])

  const fetchArchives = async () => {
    try {
      const res = await listAuditArchives()
      setArchives(res.data || [])
    } catch (e: any) { /* 忽略 */ }
  }

  const saveConfig = async () => {
    setLoading(true); setError('')
    try {
      const res = await updateAuditConfig({
        retention_days: Number(configForm.retention_days),
        archive_after_days: Number(configForm.archive_after_days),
        rotation_size_mb: Number(configForm.rotation_size_mb),
        siem_enabled: Boolean(configForm.siem_enabled),
        siem_host: configForm.siem_host,
        siem_port: Number(configForm.siem_port),
        siem_protocol: configForm.siem_protocol,
        mask_sensitive: Boolean(configForm.mask_sensitive),
      })
      setConfigForm(res.data)
      setSuccess('配置已保存')
    } catch (e: any) { setError(e?.response?.data?.detail || '保存失败') } finally { setLoading(false) }
  }

  const doArchive = async () => {
    setLoading(true); setError('')
    try {
      const res = await runAuditArchive()
      setSuccess(`归档完成：${res.data?.archived ?? 0} 条记录`)
      fetchArchives()
    } catch (e: any) { setError(e?.response?.data?.detail || '归档失败') } finally { setLoading(false) }
  }

  const doRetention = async () => {
    if (!window.confirm('将删除超过保留期的审计日志，确认执行？')) return
    setLoading(true); setError('')
    try {
      const res = await runAuditRetention()
      setSuccess(`清理完成：删除 ${res.data?.deleted ?? 0} 条过期记录`)
    } catch (e: any) { setError(e?.response?.data?.detail || '清理失败') } finally { setLoading(false) }
  }

  const [testOp, setTestOp] = useState(false)
  const doTestLog = async () => {
    setTestOp(true); setError('')
    try {
      await createAuditLog({
        operator_id: 'system', operator_name: '系统', operator_ip: '127.0.0.1',
        category: 'system', action_type: 'audit.test_write', result: 'success',
        details: { action: '测试写入审计日志' },
      })
      setSuccess('测试审计记录已写入（验证哈希链）')
      fetchLogs()
    } catch (e: any) { setError(e?.response?.data?.detail || '写入失败') } finally { setTestOp(false) }
  }

  const inputCls = 'border border-gray-300 rounded px-2 py-1 text-sm w-full'
  const btnCls = 'px-3 py-1.5 rounded text-sm bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50'
  const btnSec = 'px-3 py-1.5 rounded text-sm border border-gray-300 hover:bg-gray-50'

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">操作审计（增强）</h1>
          <p className="text-sm text-gray-500 mt-1">哈希链防篡改 · 异常行为检测 · SIEM 集成 · 合规保留</p>
        </div>
        <div className="flex gap-2">
          <button className={btnSec} onClick={doTestLog} disabled={testOp}>
            {testOp ? '写入中…' : '写入测试记录'}
          </button>
          <button className={btnSec} onClick={doVerifyChain}>校验哈希链</button>
        </div>
      </div>

      {error && <div className="bg-red-50 text-red-700 border border-red-200 rounded px-4 py-2 mb-4 text-sm">{error}</div>}
      {success && <div className="bg-green-50 text-green-700 border border-green-200 rounded px-4 py-2 mb-4 text-sm">{success}</div>}

      <div className="flex gap-1 mb-4 flex-wrap">
        {TABS.map(t => (
          <button
            key={t.key}
            onClick={() => { setActiveTab(t.key); setSuccess('') }}
            className={`px-4 py-2 rounded-t text-sm ${activeTab === t.key ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {activeTab === 'logs' && (
        <div>
          {stats && (
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
              <div className="bg-white border rounded p-3"><div className="text-2xl font-bold">{stats.total ?? 0}</div><div className="text-xs text-gray-500">总记录数</div></div>
              <div className="bg-white border rounded p-3"><div className="text-2xl font-bold">{(stats.by_category?.user ?? 0) + (stats.by_category?.agent ?? 0) + (stats.by_category?.system ?? 0) + (stats.by_category?.security ?? 0)}</div><div className="text-xs text-gray-500">分类合计</div></div>
              <div className="bg-white border rounded p-3"><div className="text-2xl font-bold">{stats.by_result?.failure ?? 0}</div><div className="text-xs text-gray-500">失败数</div></div>
              <div className="bg-white border rounded p-3"><div className="text-2xl font-bold">{stats.retention_days ?? 180}</div><div className="text-xs text-gray-500">保留期(天)</div></div>
              <div className={`bg-white border rounded p-3 ${stats.retention_compliant === false ? 'bg-red-50' : ''}`}>
                <div className="text-2xl font-bold">{stats.retention_compliant ? '合规' : '超标'}</div>
                <div className="text-xs text-gray-500">合规状态</div>
              </div>
            </div>
          )}

          <div className="bg-white border rounded p-4 mb-4">
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              <input className={inputCls} placeholder="操作者" value={filters.operator_id}
                onChange={e => setFilters({ ...filters, operator_id: e.target.value })} />
              <input className={inputCls} placeholder="操作类型 (agent.create)" value={filters.action_type}
                onChange={e => setFilters({ ...filters, action_type: e.target.value })} />
              <select className={inputCls} value={filters.category} onChange={e => setFilters({ ...filters, category: e.target.value })}>
                <option value="">全部分类</option>
                <option value="user">用户操作</option>
                <option value="agent">Agent 操作</option>
                <option value="system">系统操作</option>
                <option value="security">安全操作</option>
              </select>
              <select className={inputCls} value={filters.result} onChange={e => setFilters({ ...filters, result: e.target.value })}>
                <option value="">全部结果</option>
                <option value="success">成功</option>
                <option value="failure">失败</option>
                <option value="denied">拒绝</option>
              </select>
              <input className={inputCls} placeholder="对象 ID" value={filters.target_id}
                onChange={e => setFilters({ ...filters, target_id: e.target.value })} />
            </div>
            <div className="mt-3 flex gap-2">
              <button className={btnCls} onClick={() => { setPage(1); fetchLogs() }} disabled={loading}>查询</button>
              <button className={btnSec} onClick={() => setFilters({ operator_id: '', action_type: '', category: '', target_id: '', result: '' })}>重置</button>
            </div>
          </div>

          <div className="bg-white border rounded overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-gray-600 text-left">
                <tr>
                  <th className="px-3 py-2">时间</th>
                  <th className="px-3 py-2">操作者</th>
                  <th className="px-3 py-2">分类</th>
                  <th className="px-3 py-2">操作类型</th>
                  <th className="px-3 py-2">对象</th>
                  <th className="px-3 py-2">结果</th>
                  <th className="px-3 py-2">哈希</th>
                  <th className="px-3 py-2">已校验</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log: Row) => (
                  <tr key={log.id} className="border-t hover:bg-gray-50">
                    <td className="px-3 py-2 whitespace-nowrap">{fmt(log.timestamp)}</td>
                    <td className="px-3 py-2">{log.operator_id}</td>
                    <td className="px-3 py-2">
                      <span className={`px-2 py-0.5 rounded text-xs ${CATEGORY_COLORS[log.category] || 'bg-gray-100'}`}>{log.category}</span>
                    </td>
                    <td className="px-3 py-2 font-mono text-xs">{log.action_type}</td>
                    <td className="px-3 py-2 text-xs">{log.target_id || '-'}</td>
                    <td className="px-3 py-2">
                      <span className={`px-2 py-0.5 rounded text-xs ${RESULT_COLORS[log.result] || 'bg-gray-100'}`}>{log.result}</span>
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-gray-500" title={log.curr_hash}>{shorten(log.curr_hash)}</td>
                    <td className="px-3 py-2">{log.verified ? '✅' : '❌'}</td>
                  </tr>
                ))}
                {logs.length === 0 && !loading && (
                  <tr><td colSpan={8} className="px-3 py-8 text-center text-gray-400">暂无审计记录 — 点击右上角「写入测试记录」验证哈希链</td></tr>
                )}
              </tbody>
            </table>
            <div className="flex items-center justify-between px-3 py-2 border-t bg-gray-50 text-sm">
              <span>共 {total} 条</span>
              <div className="flex gap-2">
                <button className={btnSec} disabled={page <= 1} onClick={() => setPage(page - 1)}>上一页</button>
                <span className="py-1">第 {page} 页</span>
                <button className={btnSec} disabled={page * pageSize >= total} onClick={() => setPage(page + 1)}>下一页</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'verify' && (
        <div className="space-y-4">
          <div className="bg-white border rounded p-4">
            <h3 className="font-semibold mb-2">哈希链完整性校验</h3>
            <p className="text-sm text-gray-500 mb-3">逐条验证 prev_hash 链接与 curr_hash 自校验，任一条被篡改则整链失效。</p>
            <button className={btnCls} onClick={doVerifyChain} disabled={loading}>{loading ? '校验中…' : '执行全链校验'}</button>
            {verifyResult && (
              <div className={`mt-3 p-3 rounded text-sm ${verifyResult.chain_valid ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
                <div className="font-bold">{verifyResult.chain_valid ? '✓ 哈希链完整，未被篡改' : `✗ 检测到 ${verifyResult.tampered_count} 条被篡改记录`}</div>
                <div className="mt-1">总记录数：{verifyResult.total_records}</div>
                {verifyResult.tampered?.length > 0 && (
                  <ul className="mt-2 space-y-1 text-xs">
                    {verifyResult.tampered.map((t: any, i: number) => (
                      <li key={i}>{fmt(t.timestamp)} — {t.action_type} — {t.reason}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
          <div className="bg-white border rounded p-4">
            <h3 className="font-semibold mb-2">单条记录校验</h3>
            <div className="flex gap-2">
              <input className={inputCls} placeholder="输入审计记录 ID" value={verifyRecordId}
                onChange={e => setVerifyRecordId(e.target.value)} />
              <button className={btnCls} onClick={doVerifyRecord} disabled={loading}>校验</button>
            </div>
            {singleVerify && (
              <div className={`mt-3 p-3 rounded text-sm ${singleVerify.valid ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
                {singleVerify.valid ? '✓ 记录哈希一致' : '✗ 记录哈希不一致（已被篡改）'}
                <div className="text-xs mt-1 font-mono">{singleVerify.curr_hash}</div>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'anomalies' && (
        <div>
          <div className="flex items-center gap-3 mb-4">
            <button className={btnCls} onClick={doScan} disabled={scanning}>{scanning ? '检测中…' : '立即扫描异常行为'}</button>
            <select className={inputCls} style={{ width: 150 }} value={anomalyFilter.severity}
              onChange={e => setAnomalyFilter({ ...anomalyFilter, severity: e.target.value })}>
              <option value="">全部级别</option>
              <option value="low">低</option>
              <option value="medium">中</option>
              <option value="high">高</option>
              <option value="critical">严重</option>
            </select>
            <select className={inputCls} style={{ width: 150 }} value={anomalyFilter.status}
              onChange={e => setAnomalyFilter({ ...anomalyFilter, status: e.target.value })}>
              <option value="">全部状态</option>
              <option value="open">待处理</option>
              <option value="acknowledged">已确认</option>
              <option value="resolved">已解决</option>
            </select>
            <span className="text-sm text-gray-500">共 {anomalyTotal} 条</span>
          </div>
          <div className="bg-white border rounded overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-gray-600 text-left">
                <tr>
                  <th className="px-3 py-2">时间</th>
                  <th className="px-3 py-2">类型</th>
                  <th className="px-3 py-2">级别</th>
                  <th className="px-3 py-2">操作者</th>
                  <th className="px-3 py-2">描述</th>
                  <th className="px-3 py-2">状态</th>
                </tr>
              </thead>
              <tbody>
                {anomalies.map((a: Row) => (
                  <tr key={a.id} className="border-t hover:bg-gray-50">
                    <td className="px-3 py-2 whitespace-nowrap">{fmt(a.created_at)}</td>
                    <td className="px-3 py-2 font-mono text-xs">{a.alert_type}</td>
                    <td className="px-3 py-2">
                      <span className={`px-2 py-0.5 rounded text-xs ${SEVERITY_COLORS[a.severity]}`}>{a.severity}</span>
                    </td>
                    <td className="px-3 py-2">{a.operator_id || '-'}</td>
                    <td className="px-3 py-2 text-xs">{a.description}</td>
                    <td className="px-3 py-2">
                      <select className="text-xs border rounded px-1 py-0.5" value={a.status}
                        onChange={e => doUpdateAnomaly(a.id, e.target.value)}>
                        <option value="open">待处理</option>
                        <option value="acknowledged">已确认</option>
                        <option value="resolved">已解决</option>
                      </select>
                    </td>
                  </tr>
                ))}
                {anomalies.length === 0 && (
                  <tr><td colSpan={6} className="px-3 py-8 text-center text-gray-400">暂无异常告警</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 'rules' && (
        <div>
          <div className="flex justify-end mb-3">
            <button className={btnCls} onClick={() => setShowRuleForm(!showRuleForm)}>
              {showRuleForm ? '取消' : '新增规则'}
            </button>
          </div>
          {showRuleForm && (
            <div className="bg-white border rounded p-4 mb-4">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <input className={inputCls} placeholder="规则名称" value={ruleForm.rule_name}
                  onChange={e => setRuleForm({ ...ruleForm, rule_name: e.target.value })} />
                <select className={inputCls} value={ruleForm.rule_type} onChange={e => setRuleForm({ ...ruleForm, rule_type: e.target.value })}>
                  <option value="off_hours">凌晨操作</option>
                  <option value="high_freq_failure">高频失败</option>
                  <option value="permission_escalation">权限越界</option>
                  <option value="batch_delete">批量删除</option>
                  <option value="sensitive_op">敏感操作</option>
                </select>
                <select className={inputCls} value={ruleForm.severity} onChange={e => setRuleForm({ ...ruleForm, severity: e.target.value })}>
                  <option value="low">低</option>
                  <option value="medium">中</option>
                  <option value="high">高</option>
                  <option value="critical">严重</option>
                </select>
                <input className={inputCls} placeholder='参数 JSON (如 {"threshold":5})' value={ruleForm.params}
                  onChange={e => setRuleForm({ ...ruleForm, params: e.target.value })} />
              </div>
              <button className={`${btnCls} mt-3`} onClick={saveRule} disabled={loading}>保存规则</button>
            </div>
          )}
          <div className="bg-white border rounded overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-gray-600 text-left">
                <tr>
                  <th className="px-3 py-2">规则名称</th>
                  <th className="px-3 py-2">类型</th>
                  <th className="px-3 py-2">级别</th>
                  <th className="px-3 py-2">参数</th>
                  <th className="px-3 py-2">状态</th>
                  <th className="px-3 py-2">操作</th>
                </tr>
              </thead>
              <tbody>
                {rules.map((r: Row) => (
                  <tr key={r.id} className="border-t hover:bg-gray-50">
                    <td className="px-3 py-2">{r.rule_name}</td>
                    <td className="px-3 py-2 font-mono text-xs">{r.rule_type}</td>
                    <td className="px-3 py-2"><span className={`px-2 py-0.5 rounded text-xs ${SEVERITY_COLORS[r.severity]}`}>{r.severity}</span></td>
                    <td className="px-3 py-2 text-xs text-gray-500">{r.params}</td>
                    <td className="px-3 py-2">{r.enabled ? <span className="text-green-600">已启用</span> : <span className="text-gray-400">已停用</span>}</td>
                    <td className="px-3 py-2 flex gap-2">
                      <button className="text-xs text-blue-600" onClick={() => toggleRule(r)}>{r.enabled ? '停用' : '启用'}</button>
                      <button className="text-xs text-red-600" onClick={() => removeRule(r.id)}>删除</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 'export' && (
        <div className="grid md:grid-cols-2 gap-4">
          <div className="bg-white border rounded p-4">
            <h3 className="font-semibold mb-2">CSV 导出（合规格式）</h3>
            <p className="text-sm text-gray-500 mb-3">按当前筛选条件导出完整审计记录，包含哈希字段，符合导出格式标准。</p>
            <button className={btnCls} onClick={doExportCsv} disabled={loading}>导出 CSV</button>
          </div>
          <div className="bg-white border rounded p-4">
            <h3 className="font-semibold mb-2">SIEM 集成（Syslog）</h3>
            <p className="text-sm text-gray-500 mb-3">将审计日志转换为 RFC3164 Syslog 格式，供 SIEM 平台采集转发。</p>
            <div className="flex gap-2 mb-3">
              <input className={inputCls} style={{ width: 120 }} type="number" min={1} max={1440}
                value={siemMinutes} onChange={e => setSiemMinutes(Number(e.target.value))} />
              <span className="text-sm py-1">分钟</span>
              <button className={btnCls} onClick={doExportSiem} disabled={loading}>生成 Syslog</button>
            </div>
            {siemLines.length > 0 && (
              <pre className="bg-gray-900 text-green-400 text-xs rounded p-3 max-h-72 overflow-auto">
                {siemLines.map((l, i) => <div key={i}>{l}</div>)}
              </pre>
            )}
          </div>
        </div>
      )}

      {activeTab === 'config' && (
        <div className="grid md:grid-cols-2 gap-4">
          <div className="bg-white border rounded p-4">
            <h3 className="font-semibold mb-3">审计配置</h3>
            <div className="space-y-3">
              <div><label className="text-sm text-gray-600">合规保留期（天，≥180）</label>
                <input className={inputCls} type="number" value={configForm.retention_days ?? 180}
                  onChange={e => setConfigForm({ ...configForm, retention_days: e.target.value })} /></div>
              <div><label className="text-sm text-gray-600">自动归档阈值（天）</label>
                <input className={inputCls} type="number" value={configForm.archive_after_days ?? 90}
                  onChange={e => setConfigForm({ ...configForm, archive_after_days: e.target.value })} /></div>
              <div><label className="text-sm text-gray-600">轮转阈值（MB）</label>
                <input className={inputCls} type="number" value={configForm.rotation_size_mb ?? 10240}
                  onChange={e => setConfigForm({ ...configForm, rotation_size_mb: e.target.value })} /></div>
              <div className="flex items-center gap-2">
                <input type="checkbox" checked={!!configForm.mask_sensitive}
                  onChange={e => setConfigForm({ ...configForm, mask_sensitive: e.target.checked })} />
                <label className="text-sm text-gray-600">隐私脱敏（IP/用户ID 匿名化）</label>
              </div>
              <div className="border-t pt-3">
                <div className="flex items-center gap-2 mb-2">
                  <input type="checkbox" checked={!!configForm.siem_enabled}
                    onChange={e => setConfigForm({ ...configForm, siem_enabled: e.target.checked })} />
                  <label className="text-sm text-gray-600">启用 SIEM 集成</label>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <input className={inputCls} placeholder="主机" value={configForm.siem_host || ''}
                    onChange={e => setConfigForm({ ...configForm, siem_host: e.target.value })} />
                  <input className={inputCls} placeholder="端口" value={configForm.siem_port ?? 514}
                    onChange={e => setConfigForm({ ...configForm, siem_port: e.target.value })} />
                  <select className={inputCls} value={configForm.siem_protocol || 'syslog'}
                    onChange={e => setConfigForm({ ...configForm, siem_protocol: e.target.value })}>
                    <option value="syslog">Syslog</option>
                    <option value="udp">UDP</option>
                    <option value="tcp">TCP</option>
                  </select>
                </div>
              </div>
              <button className={btnCls} onClick={saveConfig} disabled={loading}>保存配置</button>
            </div>
          </div>
          <div className="space-y-4">
            <div className="bg-white border rounded p-4">
              <h3 className="font-semibold mb-3">归档与合规</h3>
              <div className="flex gap-2 mb-3">
                <button className={btnSec} onClick={doArchive} disabled={loading}>执行归档（冷热分离）</button>
                <button className="px-3 py-1.5 rounded text-sm bg-red-600 text-white hover:bg-red-700"
                  onClick={doRetention} disabled={loading}>清理过期记录</button>
              </div>
              <div className="text-xs text-gray-500 space-y-1">
                <div>归档：超过 {configForm.archive_after_days ?? 90} 天的记录移入冷存储</div>
                <div>保留期：{configForm.retention_days ?? 180} 天后物理删除（符合合规要求）</div>
              </div>
            </div>
            <div className="bg-white border rounded p-4">
              <h3 className="font-semibold mb-3">归档记录</h3>
              <table className="w-full text-sm">
                <thead className="text-left text-gray-500 text-xs">
                  <tr><th className="py-1">归档键</th><th className="py-1">范围</th><th className="py-1">记录数</th></tr>
                </thead>
                <tbody>
                  {archives.map((a: Row) => (
                    <tr key={a.id} className="border-t text-xs">
                      <td className="py-1.5 font-mono">{a.archive_key}</td>
                      <td className="py-1.5">{fmt(a.start_date)} ~ {fmt(a.end_date)}</td>
                      <td className="py-1.5">{a.record_count}</td>
                    </tr>
                  ))}
                  {archives.length === 0 && <tr><td colSpan={3} className="py-4 text-center text-gray-400">暂无归档记录</td></tr>}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
