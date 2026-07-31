import { useState, useEffect, useCallback } from 'react'
import {
  listBackupPolicies, upsertBackupPolicy, deleteBackupPolicy,
  createBackup, listBackups, deleteBackup, getBackupEnhancedStats,
  listBackupEvents,
  createRestore, listRestores,
  createDrill, completeDrill, listDrills, getDrillStats,
  rotateKey, listKeys,
  getBackupEnhancedDashboard,
} from '../api/backupEnhanced'

const TYPE_COLORS: Record<string, string> = {
  full: 'bg-blue-100 text-blue-700',
  incremental: 'bg-green-100 text-green-700',
  event: 'bg-purple-100 text-purple-700',
}

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-gray-100 text-gray-600',
  running: 'bg-blue-100 text-blue-700',
  success: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
  verifying: 'bg-yellow-100 text-yellow-700',
  precheck: 'bg-yellow-100 text-yellow-700',
  rolled_back: 'bg-purple-100 text-purple-700',
}

const TABS = [
  { key: 'overview', label: '概览' },
  { key: 'backups', label: '备份记录' },
  { key: 'policies', label: '备份策略' },
  { key: 'restores', label: '恢复操作' },
  { key: 'drills', label: '恢复演练' },
  { key: 'keys', label: '密钥管理' },
]

interface Row { id: string; [key: string]: any }

export default function BackupEnhancedPage() {
  const [activeTab, setActiveTab] = useState('overview')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  // overview
  const [overview, setOverview] = useState<any>(null)

  // backups
  const [backups, setBackups] = useState<Row[]>([])
  const [backupStats, setBackupStats] = useState<any>(null)
  const [backupForm, setBackupForm] = useState({ agent_id: '', agent_name: '', backup_type: 'full', scope: 'all' })

  // policies
  const [policies, setPolicies] = useState<Row[]>([])
  const [showPolicyForm, setShowPolicyForm] = useState(false)
  const [policyForm, setPolicyForm] = useState<any>({
    agent_id: '', agent_name: '', full_backup_cron: '0 3 * * *',
    incremental_interval_hours: 6, event_trigger_enabled: true,
    encryption_enabled: true, retention_full_count: 7,
    retention_incremental_count: 48, retention_days: 90,
    drill_enabled: true, drill_cron: '0 4 * * 0', default_scope: 'all',
  })

  // restores
  const [restores, setRestores] = useState<Row[]>([])
  const [showRestoreForm, setShowRestoreForm] = useState(false)
  const [restoreForm, setRestoreForm] = useState({ backup_id: '', restore_type: 'full', target_agent_id: '', target_agent_name: '' })

  // drills
  const [drills, setDrills] = useState<Row[]>([])
  const [drillStats, setDrillStats] = useState<any>(null)
  const [showDrillForm, setShowDrillForm] = useState(false)
  const [drillForm, setDrillForm] = useState({ agent_id: '', agent_name: '', backup_id: '' })

  // keys
  const [keys, setKeys] = useState<Row[]>([])

  // events
  const [events, setEvents] = useState<Row[]>([])

  const fetchOverview = useCallback(async () => {
    try { setOverview((await getBackupEnhancedDashboard()).data) } catch (e: any) { setError(e?.message || '加载概览失败') }
  }, [])

  const fetchBackups = useCallback(async () => {
    try {
      const [b, s] = await Promise.all([listBackups({ limit: 50 }), getBackupEnhancedStats(30)])
      setBackups(b.data?.items || [])
      setBackupStats(s.data?.data)
    } catch (e: any) { setError(e?.message || '加载备份失败') }
  }, [])

  const fetchPolicies = useCallback(async () => {
    try { setPolicies((await listBackupPolicies({ limit: 50 })).data?.items || []) } catch (e: any) { setError(e?.message || '加载策略失败') }
  }, [])

  const fetchRestores = useCallback(async () => {
    try { setRestores((await listRestores({ limit: 50 })).data?.items || []) } catch (e: any) { setError(e?.message || '加载恢复失败') }
  }, [])

  const fetchDrills = useCallback(async () => {
    try {
      const [d, s] = await Promise.all([listDrills({ limit: 50 }), getDrillStats(90)])
      setDrills(d.data?.items || [])
      setDrillStats(s.data?.data)
    } catch (e: any) { setError(e?.message || '加载演练失败') }
  }, [])

  const fetchKeys = useCallback(async () => {
    try { setKeys((await listKeys()).data?.items || []) } catch (e: any) { setError(e?.message || '加载密钥失败') }
  }, [])

  const fetchEvents = useCallback(async () => {
    try { setEvents((await listBackupEvents({ limit: 30 })).data?.items || []) } catch (e: any) { /* silent */ }
  }, [])

  useEffect(() => {
    setLoading(true)
    Promise.all([fetchOverview(), fetchBackups(), fetchPolicies(), fetchRestores(), fetchDrills(), fetchKeys(), fetchEvents()])
      .finally(() => setLoading(false))
  }, [fetchOverview, fetchBackups, fetchPolicies, fetchRestores, fetchDrills, fetchKeys, fetchEvents])

  const handleCreateBackup = async () => {
    try {
      const r = await createBackup({ ...backupForm, agent_name: backupForm.agent_name || backupForm.agent_id })
      setSuccess(r.data?.message || '备份完成')
      setBackupForm({ agent_id: '', agent_name: '', backup_type: 'full', scope: 'all' })
      fetchBackups(); fetchOverview()
    } catch (e: any) { setError(e?.message || '创建备份失败') }
  }

  const handleSavePolicy = async () => {
    try {
      await upsertBackupPolicy({ ...policyForm, agent_name: policyForm.agent_name || policyForm.agent_id })
      setSuccess('策略已保存')
      setShowPolicyForm(false)
      setPolicyForm({ agent_id: '', agent_name: '', full_backup_cron: '0 3 * * *', incremental_interval_hours: 6, event_trigger_enabled: true, encryption_enabled: true, retention_full_count: 7, retention_incremental_count: 48, retention_days: 90, drill_enabled: true, drill_cron: '0 4 * * 0', default_scope: 'all' })
      fetchPolicies(); fetchOverview()
    } catch (e: any) { setError(e?.message || '保存策略失败') }
  }

  const handleRestore = async () => {
    try {
      const r = await createRestore({ ...restoreForm, target_agent_name: restoreForm.target_agent_name || restoreForm.target_agent_id })
      setSuccess(r.data?.message || '恢复完成')
      setShowRestoreForm(false)
      setRestoreForm({ backup_id: '', restore_type: 'full', target_agent_id: '', target_agent_name: '' })
      fetchRestores()
    } catch (e: any) { setError(e?.message || '恢复失败') }
  }

  const handleCreateDrill = async () => {
    try {
      await createDrill({ ...drillForm, agent_name: drillForm.agent_name || drillForm.agent_id })
      setSuccess('演练已创建')
      setShowDrillForm(false)
      setDrillForm({ agent_id: '', agent_name: '', backup_id: '' })
      fetchDrills()
    } catch (e: any) { setError(e?.message || '创建演练失败') }
  }

  const handleRotateKey = async () => {
    try {
      const r = await rotateKey('manual rotation')
      setSuccess(r.data?.message || '密钥已轮换')
      fetchKeys(); fetchOverview()
    } catch (e: any) { setError(e?.message || '轮换密钥失败') }
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">各智能体备份与恢复（增强）</h1>
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

      {/* ===== 概览 ===== */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard title="30天备份数" value={overview?.stats?.total ?? '-'} desc={`成功率 ${overview?.stats?.success_rate ?? '-'}%`} />
            <StatCard title="加密备份" value={overview?.encrypted_backups ?? '-'} desc="AES-256-GCM" />
            <StatCard title="启用策略" value={overview?.active_policies ?? '-'} />
            <StatCard title="演练成功率" value={overview?.drills?.success_rate != null ? `${overview.drills.success_rate}%` : '-'} desc={`${overview?.drills?.total ?? 0} 次演练`} />
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <section className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <h3 className="font-semibold text-gray-800 mb-3">最近备份</h3>
              <DataTable
                rows={overview?.recent_backups || []}
                cols={[
                  { key: 'agent_name', label: 'Agent' },
                  { key: 'backup_type', label: '类型', render: v => <Badge text={v} map={TYPE_COLORS} /> },
                  { key: 'scope', label: '范围' },
                  { key: 'encryption_algo', label: '加密', render: v => (v === 'aes_256_gcm' ? '🔒' : '-') },
                  { key: 'status', label: '状态', render: v => <Badge text={v} map={STATUS_COLORS} /> },
                  { key: 'created_at', label: '时间', render: v => fmtTime(v) },
                ]}
              />
            </section>
            <section className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <h3 className="font-semibold text-gray-800 mb-3">最近事件备份</h3>
              <DataTable
                rows={events}
                cols={[
                  { key: 'agent_id', label: 'Agent' },
                  { key: 'event_type', label: '事件' },
                  { key: 'status', label: '状态', render: v => <Badge text={v} map={{ processed: 'bg-green-100 text-green-700', skipped: 'bg-gray-100 text-gray-600', failed: 'bg-red-100 text-red-700' }} /> },
                  { key: 'triggered_at', label: '时间', render: v => fmtTime(v) },
                ]}
              />
            </section>
          </div>
        </div>
      )}

      {/* ===== 备份记录 ===== */}
      {activeTab === 'backups' && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <StatCard title="备份总数" value={backupStats?.total ?? '-'} />
            <StatCard title="成功" value={backupStats?.success ?? '-'} />
            <StatCard title="失败" value={backupStats?.failed ?? '-'} />
            <StatCard title="全量/增量" value={`${backupStats?.full_backups ?? 0}/${backupStats?.incremental_backups ?? 0}`} />
            <StatCard title="总大小" value={backupStats?.total_bytes ? fmtBytes(backupStats.total_bytes) : '-'} />
          </div>
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 space-y-3">
            <h3 className="font-semibold text-gray-800">创建备份</h3>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              <input value={backupForm.agent_id} onChange={e => setBackupForm({ ...backupForm, agent_id: e.target.value })}
                className="p-2 border border-gray-200 rounded-lg text-sm" placeholder="Agent ID" />
              <input value={backupForm.agent_name} onChange={e => setBackupForm({ ...backupForm, agent_name: e.target.value })}
                className="p-2 border border-gray-200 rounded-lg text-sm" placeholder="Agent 名称" />
              <select value={backupForm.backup_type} onChange={e => setBackupForm({ ...backupForm, backup_type: e.target.value })}
                className="p-2 border border-gray-200 rounded-lg text-sm">
                <option value="full">全量备份</option>
                <option value="incremental">增量备份</option>
                <option value="event">事件备份</option>
              </select>
              <select value={backupForm.scope} onChange={e => setBackupForm({ ...backupForm, scope: e.target.value })}
                className="p-2 border border-gray-200 rounded-lg text-sm">
                <option value="all">全部</option>
                <option value="config">仅配置</option>
                <option value="memory">仅记忆</option>
                <option value="conversations">仅会话</option>
              </select>
              <button onClick={handleCreateBackup} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">立即备份</button>
            </div>
          </div>
          <section className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            <h3 className="font-semibold text-gray-800 mb-3">备份列表</h3>
            <DataTable
              rows={backups}
              cols={[
                { key: 'agent_name', label: 'Agent' },
                { key: 'backup_type', label: '类型', render: v => <Badge text={v} map={TYPE_COLORS} /> },
                { key: 'scope', label: '范围' },
                { key: 'status', label: '状态', render: v => <Badge text={v} map={STATUS_COLORS} /> },
                { key: 'size_bytes', label: '大小', render: v => (v != null ? fmtBytes(v) : '-') },
                { key: 'encryption_algo', label: '加密', render: v => (v === 'aes_256_gcm' ? '🔒' : '-') },
                { key: 'checksum_sha256', label: 'SHA-256', render: v => (v ? v.slice(0, 12) + '...' : '-') },
                { key: 'base_backup_id', label: '基础备份', render: v => (v ? v.slice(0, 8) + '...' : '-') },
                { key: 'created_at', label: '时间', render: v => fmtTime(v) },
                { key: 'id', label: '操作', render: (_, row) => (
                  <button onClick={() => deleteBackup(row.id).then(() => { fetchBackups(); fetchOverview() })} className="text-xs text-red-600 hover:underline">删除</button>
                ) },
              ]}
            />
          </section>
        </div>
      )}

      {/* ===== 备份策略 ===== */}
      {activeTab === 'policies' && (
        <div className="space-y-6">
          <div className="flex justify-end">
            <button onClick={() => setShowPolicyForm(!showPolicyForm)} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">
              {showPolicyForm ? '取消' : '+ 新建策略'}
            </button>
          </div>
          {showPolicyForm && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 space-y-3">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
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
                  <label className="block text-sm text-gray-600 mb-1">全量备份 Cron</label>
                  <input value={policyForm.full_backup_cron} onChange={e => setPolicyForm({ ...policyForm, full_backup_cron: e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm font-mono" />
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">增量间隔(小时)</label>
                  <input type="number" value={policyForm.incremental_interval_hours} onChange={e => setPolicyForm({ ...policyForm, incremental_interval_hours: +e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm" />
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">保留全量数</label>
                  <input type="number" value={policyForm.retention_full_count} onChange={e => setPolicyForm({ ...policyForm, retention_full_count: +e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm" />
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">保留增量数</label>
                  <input type="number" value={policyForm.retention_incremental_count} onChange={e => setPolicyForm({ ...policyForm, retention_incremental_count: +e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm" />
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">保留天数</label>
                  <input type="number" value={policyForm.retention_days} onChange={e => setPolicyForm({ ...policyForm, retention_days: +e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm" />
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">演练 Cron</label>
                  <input value={policyForm.drill_cron} onChange={e => setPolicyForm({ ...policyForm, drill_cron: e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm font-mono" />
                </div>
              </div>
              <div className="flex gap-6">
                <label className="flex items-center gap-2 text-sm text-gray-600">
                  <input type="checkbox" checked={policyForm.encryption_enabled} onChange={e => setPolicyForm({ ...policyForm, encryption_enabled: e.target.checked })} />
                  AES-256 加密
                </label>
                <label className="flex items-center gap-2 text-sm text-gray-600">
                  <input type="checkbox" checked={policyForm.event_trigger_enabled} onChange={e => setPolicyForm({ ...policyForm, event_trigger_enabled: e.target.checked })} />
                  事件触发备份
                </label>
                <label className="flex items-center gap-2 text-sm text-gray-600">
                  <input type="checkbox" checked={policyForm.drill_enabled} onChange={e => setPolicyForm({ ...policyForm, drill_enabled: e.target.checked })} />
                  自动演练
                </label>
              </div>
              <button onClick={handleSavePolicy} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">保存策略</button>
            </div>
          )}
          <section className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            <h3 className="font-semibold text-gray-800 mb-3">策略列表</h3>
            <DataTable
              rows={policies}
              cols={[
                { key: 'agent_name', label: 'Agent' },
                { key: 'full_backup_cron', label: '全量 Cron' },
                { key: 'incremental_interval_hours', label: '增量间隔' },
                { key: 'encryption_enabled', label: '加密', render: v => (v ? '🔒' : '-') },
                { key: 'event_trigger_enabled', label: '事件触发', render: v => (v ? '✅' : '❌') },
                { key: 'retention_full_count', label: '保留全量' },
                { key: 'retention_days', label: '保留天数' },
                { key: 'enabled', label: '启用', render: v => (v ? '✅' : '❌') },
                { key: 'id', label: '操作', render: (_, row) => (
                  <button onClick={() => deleteBackupPolicy(row.id).then(fetchPolicies)} className="text-xs text-red-600 hover:underline">停用</button>
                ) },
              ]}
            />
          </section>
        </div>
      )}

      {/* ===== 恢复操作 ===== */}
      {activeTab === 'restores' && (
        <div className="space-y-6">
          <div className="flex justify-end">
            <button onClick={() => setShowRestoreForm(!showRestoreForm)} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">
              {showRestoreForm ? '取消' : '+ 新建恢复'}
            </button>
          </div>
          {showRestoreForm && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 space-y-3">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <label className="block text-sm text-gray-600 mb-1">备份 ID</label>
                  <input value={restoreForm.backup_id} onChange={e => setRestoreForm({ ...restoreForm, backup_id: e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm" placeholder="备份记录 ID" />
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">恢复类型</label>
                  <select value={restoreForm.restore_type} onChange={e => setRestoreForm({ ...restoreForm, restore_type: e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm">
                    <option value="full">完整恢复</option>
                    <option value="config">仅配置</option>
                    <option value="memory">仅记忆</option>
                    <option value="conversations">仅会话</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">目标 Agent ID</label>
                  <input value={restoreForm.target_agent_id} onChange={e => setRestoreForm({ ...restoreForm, target_agent_id: e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm" placeholder="支持跨 Agent 恢复" />
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">目标 Agent 名称</label>
                  <input value={restoreForm.target_agent_name} onChange={e => setRestoreForm({ ...restoreForm, target_agent_name: e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm" placeholder="可选" />
                </div>
              </div>
              <button onClick={handleRestore} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">执行恢复</button>
            </div>
          )}
          <section className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            <h3 className="font-semibold text-gray-800 mb-3">恢复记录</h3>
            <DataTable
              rows={restores}
              cols={[
                { key: 'source_agent_name', label: '来源' },
                { key: 'target_agent_name', label: '目标' },
                { key: 'restore_type', label: '类型' },
                { key: 'status', label: '状态', render: v => <Badge text={v} map={STATUS_COLORS} /> },
                { key: 'health_score_after', label: '恢复后健康分', render: v => (v != null ? v : '-') },
                { key: 'error_message', label: '错误', render: v => (v ? <span className="text-red-600">{v}</span> : '-') },
                { key: 'created_at', label: '时间', render: v => fmtTime(v) },
              ]}
            />
          </section>
        </div>
      )}

      {/* ===== 恢复演练 ===== */}
      {activeTab === 'drills' && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard title="演练总数" value={drillStats?.total ?? '-'} />
            <StatCard title="成功" value={drillStats?.success ?? '-'} />
            <StatCard title="失败" value={drillStats?.failed ?? '-'} />
            <StatCard title="成功率" value={drillStats?.success_rate != null ? `${drillStats.success_rate}%` : '-'} />
          </div>
          <div className="flex justify-end">
            <button onClick={() => setShowDrillForm(!showDrillForm)} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">
              {showDrillForm ? '取消' : '+ 新建演练'}
            </button>
          </div>
          {showDrillForm && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 space-y-3">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <label className="block text-sm text-gray-600 mb-1">Agent ID</label>
                  <input value={drillForm.agent_id} onChange={e => setDrillForm({ ...drillForm, agent_id: e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm" />
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">Agent 名称</label>
                  <input value={drillForm.agent_name} onChange={e => setDrillForm({ ...drillForm, agent_name: e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm" />
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">备份 ID</label>
                  <input value={drillForm.backup_id} onChange={e => setDrillForm({ ...drillForm, backup_id: e.target.value })}
                    className="w-full p-2 border border-gray-200 rounded-lg text-sm" placeholder="选择要验证的备份" />
                </div>
              </div>
              <button onClick={handleCreateDrill} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">创建演练</button>
            </div>
          )}
          <section className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            <h3 className="font-semibold text-gray-800 mb-3">演练记录</h3>
            <DataTable
              rows={drills}
              cols={[
                { key: 'agent_name', label: 'Agent' },
                { key: 'backup_id', label: '备份', render: v => v.slice(0, 8) + '...' },
                { key: 'status', label: '状态', render: v => <Badge text={v} map={{ scheduled: 'bg-gray-100 text-gray-600', running: 'bg-blue-100 text-blue-700', success: 'bg-green-100 text-green-700', failed: 'bg-red-100 text-red-700' }} /> },
                { key: 'restore_ok', label: '恢复OK', render: v => (v === true ? '✅' : v === false ? '❌' : '-') },
                { key: 'duration_seconds', label: '耗时(s)', render: v => (v != null ? v.toFixed(1) : '-') },
                { key: 'scheduled_at', label: '时间', render: v => fmtTime(v) },
                { key: 'id', label: '操作', render: (_, row) => (
                  <button onClick={() => completeDrill(row.id, { restore_ok: true, report_data: { checked: 'full' } }).then(fetchDrills)}
                    className="text-xs text-green-600 hover:underline">标记成功</button>
                ) },
              ]}
            />
          </section>
        </div>
      )}

      {/* ===== 密钥管理 ===== */}
      {activeTab === 'keys' && (
        <div className="space-y-6">
          <div className="flex justify-end">
            <button onClick={handleRotateKey} className="px-4 py-2 bg-orange-600 text-white text-sm rounded-lg hover:bg-orange-700">🔄 轮换密钥</button>
          </div>
          <section className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            <h3 className="font-semibold text-gray-800 mb-1">加密密钥</h3>
            <p className="text-sm text-gray-500 mb-3">密钥以 AES-256 加密保存于本地密钥库，旧备份仍可用旧密钥解密（保留密钥）。轮换后新备份使用新密钥。</p>
            <DataTable
              rows={keys}
              cols={[
                { key: 'key_id', label: 'Key ID' },
                { key: 'algorithm', label: '算法' },
                { key: 'status', label: '状态', render: v => <Badge text={v} map={{ active: 'bg-green-100 text-green-700', retired: 'bg-gray-100 text-gray-600' }} /> },
                { key: 'created_at', label: '创建时间', render: v => fmtTime(v) },
                { key: 'note', label: '备注', render: v => (v || '-') },
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

function fmtTime(v: any): string {
  if (!v) return '-'
  const d = new Date(v)
  if (isNaN(d.getTime())) return String(v)
  return d.toLocaleString('zh-CN', { hour12: false })
}

function fmtBytes(b: number): string {
  if (!b) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  while (b >= 1024 && i < units.length - 1) { b /= 1024; i++ }
  return `${b.toFixed(1)} ${units[i]}`
}
