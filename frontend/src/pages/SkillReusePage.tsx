import React, { useEffect, useState, useCallback } from 'react'
import {
  createReuse, removeReuse, listReuses,
  checkUpdates, syncReuse, syncAllReuses,
  getReuseStats, getReuseRanking, getReuseGraph,
  SkillReuseRelation,
} from '../api/skillReuse'
import apiFetch from '../api/client'
import { useToast } from '../components/ui'

const SkillReusePage: React.FC = () => {
  const toast = useToast()
  const [tab, setTab] = useState<'list' | 'create' | 'sync' | 'stats'>('list')

  // 列表
  const [relations, setRelations] = useState<SkillReuseRelation[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)

  // 创建
  const [skills, setSkills] = useState<any[]>([])
  const [agents, setAgents] = useState<any[]>([])
  const [createForm, setCreateForm] = useState({ source_skill_id: '', target_agent_id: '', reuse_mode: 'direct_ref', sync_mode: 'manual' })
  const [creating, setCreating] = useState(false)

  // 同步
  const [updates, setUpdates] = useState<Array<Record<string, unknown>>>([])
  const [checkingSkillId, setCheckingSkillId] = useState('')
  const [syncing, setSyncing] = useState(false)

  // 统计
  const [statsSkillId, setStatsSkillId] = useState('')
  const [stats, setStats] = useState<Record<string, unknown> | null>(null)
  const [ranking, setRanking] = useState<Array<Record<string, unknown>>>([])
  const [graph, setGraph] = useState<{ nodes: any[]; edges: any[] } | null>(null)

  const loadList = useCallback(async () => {
    setLoading(true)
    try {
      const result = await listReuses({ offset: 0, limit: 50 })
      setRelations(result.data || [])
      setTotal(result.total)
    } catch { toast.error('加载失败') }
    finally { setLoading(false) }
  }, [toast])

  useEffect(() => { if (tab === 'list') loadList() }, [tab])

  const loadOptions = async () => {
    try {
      const [s, a] = await Promise.all([
        apiFetch('/api/v1/skills', { method: 'GET' }),
        apiFetch('/api/v1/agents', { method: 'GET' }),
      ])
      const skillsData = s.data?.data || s.data || []
      const agentsData = a.data?.data || a.data || []
      setSkills(Array.isArray(skillsData) ? skillsData : [])
      setAgents(Array.isArray(agentsData) ? agentsData : [])
    } catch { toast.error('加载选项失败') }
  }

  useEffect(() => { if (tab === 'create') loadOptions() }, [tab])

  const handleCreate = async () => {
    if (!createForm.source_skill_id || !createForm.target_agent_id) { toast.error('请选择 Skill 和 Agent'); return }
    setCreating(true)
    try {
      await createReuse(createForm.source_skill_id, createForm.target_agent_id, createForm.reuse_mode, createForm.sync_mode)
      toast.success('复用关系已创建')
      setCreateForm({ source_skill_id: '', target_agent_id: '', reuse_mode: 'direct_ref', sync_mode: 'manual' })
      loadList()
      setTab('list')
    } catch { toast.error('创建失败') }
    finally { setCreating(false) }
  }

  const handleRemove = async (id: string) => {
    if (!confirm('删除复用关系后不再接收同步更新，确认删除？')) return
    try {
      await removeReuse(id)
      toast.success('已删除')
      loadList()
    } catch { toast.error('删除失败') }
  }

  const handleCheckUpdates = async () => {
    if (!checkingSkillId.trim()) { toast.error('请输入 Skill ID'); return }
    try {
      const data = await checkUpdates(checkingSkillId)
      setUpdates(data)
      if (data.length === 0) toast.success('没有更新需要同步')
    } catch { toast.error('检查失败') }
  }

  const handleSyncOne = async (relationId: string) => {
    try {
      await syncReuse(relationId)
      toast.success('同步完成')
      handleCheckUpdates()
    } catch { toast.error('同步失败') }
  }

  const handleSyncAll = async () => {
    if (!checkingSkillId.trim()) return
    setSyncing(true)
    try {
      const result = await syncAllReuses(checkingSkillId)
      toast.success(`已同步 ${result.total} 个复用关系`)
      setUpdates([])
    } catch { toast.error('同步失败') }
    finally { setSyncing(false) }
  }

  const handleLoadStats = async () => {
    if (!statsSkillId.trim()) { toast.error('请输入 Skill ID'); return }
    try {
      const [s, r, g] = await Promise.all([
        getReuseStats(statsSkillId),
        getReuseRanking(10),
        getReuseGraph(statsSkillId).catch(() => ({ nodes: [], edges: [] })),
      ])
      setStats(s)
      setRanking(r)
      setGraph(g)
    } catch { toast.error('加载统计失败') }
  }

  const renderModeBadge = (mode: string) => {
    const m: Record<string, [string, string]> = {
      direct_ref: ['🔗 直接引用', 'bg-blue-100 text-blue-700'],
      copy: ['📋 复制', 'bg-green-100 text-green-700'],
      template: ['📐 模板', 'bg-purple-100 text-purple-700'],
    }
    const [label, cls] = m[mode] || [mode, 'bg-gray-100']
    return <span className={`px-2 py-0.5 rounded text-xs font-medium ${cls}`}>{label}</span>
  }

  const renderStatusBadge = (status: string) => {
    const m: Record<string, [string, string]> = {
      active: ['✅ 正常', 'bg-green-100 text-green-700'],
      outdated: ['🔄 有更新', 'bg-yellow-100 text-yellow-700'],
      modified: ['✏️ 已修改', 'bg-orange-100 text-orange-700'],
      conflict: ['⚠️ 冲突', 'bg-red-100 text-red-700'],
    }
    const [label, cls] = m[status] || [status, 'bg-gray-100']
    return <span className={`px-2 py-0.5 rounded text-xs font-medium ${cls}`}>{label}</span>
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold flex items-center gap-2">🔄 Skill 跨 Agent 复用</h1>
        <p className="text-gray-500 mt-1">直接引用 · 复制 · 模板 — 变更通知 · 关系图 · 复用排行</p>
      </div>

      <div className="flex gap-1 mb-6 border-b">
        {[
          { key: 'list', label: '🔗 复用关系' },
          { key: 'create', label: '➕ 新建复用' },
          { key: 'sync', label: '🔄 同步管理' },
          { key: 'stats', label: '📊 统计排行' },
        ].map(t => (
          <button key={t.key} onClick={() => setTab(t.key as any)}
            className={`px-4 py-2 text-sm border-b-2 ${tab === t.key ? 'border-blue-500 text-blue-600 font-medium' : 'border-transparent text-gray-500'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* 关系列表 */}
      {tab === 'list' && (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="px-5 py-3 border-b bg-gray-50 text-sm font-semibold">复用关系 ({total})</div>
          {loading ? (
            <div className="flex justify-center py-12"><div className="animate-spin w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full" /></div>
          ) : relations.length === 0 ? (
            <div className="text-center py-12 text-gray-400 text-sm">暂无复用关系</div>
          ) : (
            <div className="divide-y">
              {relations.map(r => (
                <div key={r.id} className="px-5 py-4 text-sm">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        {renderModeBadge(r.reuse_mode)}
                        {renderStatusBadge(r.status)}
                        <span className="text-xs text-gray-400">{r.sync_mode === 'auto' ? '🔄' : r.sync_mode === 'manual' ? '✋' : '🚫'}</span>
                      </div>
                      <div className="flex items-center gap-2 mt-1">
                        <code className="text-xs bg-gray-100 px-1 py-0.5 rounded">{r.source_skill_name || r.source_skill_id.slice(0, 12)}</code>
                        <span className="text-gray-400">→</span>
                        <code className="text-xs bg-gray-100 px-1 py-0.5 rounded">{r.target_skill_name || r.target_skill_id.slice(0, 12)}</code>
                        <span className="text-gray-300 mx-1">|</span>
                        <code className="text-xs text-gray-500">{r.target_agent_id.slice(0, 12)}...</code>
                      </div>
                      <div className="flex gap-3 mt-1 text-xs text-gray-400">
                        <span>版本: {r.synced_version || '-'}</span>
                        <span>复用 {r.reuse_count} 次</span>
                        {r.last_synced_at && <span>同步: {new Date(r.last_synced_at).toLocaleString()}</span>}
                      </div>
                    </div>
                    <div className="flex gap-1 ml-3">
                      {r.status === 'outdated' && (
                        <button onClick={() => handleSyncOne(r.id)}
                          className="px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200">同步</button>
                      )}
                      <button onClick={() => handleRemove(r.id)}
                        className="px-2 py-1 text-xs text-red-500 hover:bg-red-50 rounded">删除</button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 新建 */}
      {tab === 'create' && (
        <div className="bg-white border border-gray-200 rounded-xl p-6 max-w-2xl">
          <h3 className="font-semibold mb-4">新建跨 Agent 复用关系</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">源 Skill</label>
              <select value={createForm.source_skill_id} onChange={e => setCreateForm(f => ({ ...f, source_skill_id: e.target.value }))}
                className="w-full px-3 py-2 border rounded-lg text-sm">
                <option value="">选择 Skill...</option>
                {skills.map((s: any) => <option key={s.id} value={s.id}>{s.name || s.title || s.id}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">目标 Agent</label>
              <select value={createForm.target_agent_id} onChange={e => setCreateForm(f => ({ ...f, target_agent_id: e.target.value }))}
                className="w-full px-3 py-2 border rounded-lg text-sm">
                <option value="">选择目标 Agent...</option>
                {agents.map((a: any) => <option key={a.id} value={a.id}>{a.name || a.id}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">复用模式</label>
              <div className="grid grid-cols-3 gap-3">
                {[
                  { value: 'direct_ref', label: '🔗 直接引用', desc: '共享同一个 Skill，变更影响所有引用者', color: 'border-blue-300' },
                  { value: 'copy', label: '📋 复制', desc: '独立复制一份，各自修改互不影响', color: 'border-green-300' },
                  { value: 'template', label: '📐 模板', desc: '从模板派生，模板更新可通知派生实例', color: 'border-purple-300' },
                ].map(m => (
                  <div key={m.value} onClick={() => setCreateForm(f => ({ ...f, reuse_mode: m.value }))}
                    className={`border-2 rounded-xl p-3 cursor-pointer transition-colors ${createForm.reuse_mode === m.value ? `${m.color} bg-blue-50` : 'border-gray-200 hover:border-gray-300'}`}>
                    <div className="text-sm font-medium">{m.label}</div>
                    <div className="text-xs text-gray-500 mt-1">{m.desc}</div>
                  </div>
                ))}
              </div>
            </div>
            {createForm.reuse_mode !== 'copy' && (
              <div>
                <label className="block text-sm font-medium mb-1">同步模式</label>
                <div className="flex gap-3">
                  {[
                    { value: 'auto', label: '🔄 自动同步', desc: '源更新自动推送' },
                    { value: 'manual', label: '✋ 手动同步', desc: '需手动触发同步' },
                    { value: 'none', label: '🚫 不同步', desc: '完全独立' },
                  ].map(m => (
                    <label key={m.value} className={`flex-1 border-2 rounded-xl p-3 cursor-pointer ${createForm.sync_mode === m.value ? 'border-blue-300 bg-blue-50' : 'border-gray-200'}`}>
                      <input type="radio" name="sync_mode" value={m.value} checked={createForm.sync_mode === m.value}
                        onChange={() => setCreateForm(f => ({ ...f, sync_mode: m.value }))} className="mr-1" />
                      <div className="text-xs font-medium">{m.label}</div>
                      <div className="text-xs text-gray-400">{m.desc}</div>
                    </label>
                  ))}
                </div>
              </div>
            )}
            <button onClick={handleCreate} disabled={creating || !createForm.source_skill_id || !createForm.target_agent_id}
              className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50">
              {creating ? '创建中...' : '创建复用关系'}
            </button>
          </div>
        </div>
      )}

      {/* 同步 */}
      {tab === 'sync' && (
        <div className="space-y-4">
          <div className="bg-white border border-gray-200 rounded-xl p-5">
            <div className="flex items-end gap-3 mb-4">
              <div className="flex-1 max-w-md">
                <label className="block text-sm font-medium mb-1">源 Skill ID</label>
                <input type="text" value={checkingSkillId} onChange={e => setCheckingSkillId(e.target.value)}
                  placeholder="输入 Skill ID 检查更新" className="w-full px-3 py-2 border rounded-lg text-sm" />
              </div>
              <button onClick={handleCheckUpdates} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm">检查更新</button>
              {updates.length > 0 && (
                <button onClick={handleSyncAll} disabled={syncing}
                  className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm disabled:opacity-50">
                  {syncing ? '同步中...' : `同步全部 (${updates.length})`}
                </button>
              )}
            </div>

            {updates.length > 0 ? (
              <div className="border border-gray-200 rounded-lg divide-y">
                <div className="px-4 py-2 bg-yellow-50 text-xs text-yellow-700 font-medium">检测到 {updates.length} 个需要同步的复用关系</div>
                {updates.map((u: any) => (
                  <div key={u.relation_id} className="px-4 py-3 flex items-center justify-between text-sm">
                    <div>
                      <div className="flex items-center gap-2">
                        <code className="text-xs bg-gray-100 px-1">{u.target_skill_name || u.target_skill_id?.slice(0, 12)}</code>
                        <span className="text-gray-400">→</span>
                        <code className="text-xs text-gray-500">{u.target_agent_id?.slice(0, 12)}...</code>
                      </div>
                      <div className="text-xs text-gray-400 mt-0.5">
                        v{u.current_version || '-'} → v{u.new_version || '-'} | {u.reuse_mode} | {u.sync_mode}
                      </div>
                    </div>
                    <button onClick={() => handleSyncOne(u.relation_id)}
                      className="px-3 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200">同步</button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-400 text-sm">输入 Skill ID 并点击检查更新</div>
            )}
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-xs text-blue-700">
            <strong>💡 同步说明：</strong>
            <ul className="mt-1 list-disc ml-4 space-y-0.5">
              <li>直接引用模式 (direct_ref)：目标 Agent 直接使用源 Skill，源更新即时生效</li>
              <li>复制模式 (copy)：同步会更新目标 Skill 的配置和代码（独立复制互不影响）</li>
              <li>模板模式 (template)：同步会更新派生 Skill 的模板参数（可保留自定义修改）</li>
              <li>自动同步源更新后会自动推送，手动同步需在此页面触发</li>
            </ul>
          </div>
        </div>
      )}

      {/* 统计 */}
      {tab === 'stats' && (
        <div className="space-y-4">
          <div className="bg-white border border-gray-200 rounded-xl p-5">
            <div className="flex items-end gap-3">
              <div className="flex-1 max-w-md">
                <label className="block text-sm font-medium mb-1">Skill ID</label>
                <input type="text" value={statsSkillId} onChange={e => setStatsSkillId(e.target.value)}
                  className="w-full px-3 py-2 border rounded-lg text-sm" />
              </div>
              <button onClick={handleLoadStats} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm">加载统计</button>
            </div>
          </div>

          {stats && (
            <>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                {[
                  { label: '总复用', value: String(stats.total_reuses ?? 0), color: 'bg-blue-50 text-blue-700' },
                  { label: '唯一 Agent', value: String(stats.unique_agents ?? 0), color: 'bg-green-50 text-green-700' },
                  ...Object.entries(stats.by_mode as Record<string, number> || {}).map(([k, v]) => ({
                    label: `模式: ${k}`, value: String(v), color: 'bg-purple-50 text-purple-700'
                  })),
                  ...Object.entries(stats.by_status as Record<string, number> || {}).map(([k, v]) => ({
                    label: `状态: ${k}`, value: String(v), color: 'bg-yellow-50 text-yellow-700'
                  })),
                ].map(c => (
                  <div key={c.label} className={`rounded-xl p-4 ${c.color}`}>
                    <div className="text-xs opacity-70">{c.label}</div>
                    <div className="text-lg font-bold mt-0.5">{c.value}</div>
                  </div>
                ))}
              </div>

              {/* 排行 */}
              {ranking.length > 0 && (
                <div className="bg-white border border-gray-200 rounded-xl">
                  <div className="px-5 py-3 border-b bg-gray-50 text-sm font-semibold">复用排行 Top {ranking.length}</div>
                  <div className="divide-y">
                    {ranking.map((r: any, i: number) => (
                      <div key={r.skill_id} className="px-5 py-3 flex items-center justify-between text-sm">
                        <div className="flex items-center gap-3">
                          <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold text-white
                            ${i === 0 ? 'bg-yellow-400' : i === 1 ? 'bg-gray-400' : i === 2 ? 'bg-orange-400' : 'bg-gray-200 text-gray-500'}`}>{i + 1}</span>
                          <div>
                            <span className="font-medium">{r.skill_name || r.skill_id.slice(0, 12)}</span>
                            <span className="text-gray-400 text-xs ml-2">ID: {r.skill_id.slice(0, 12)}...</span>
                          </div>
                        </div>
                        <div className="flex gap-4 text-xs text-gray-500">
                          <span>复用 {r.reuse_count} 次</span>
                          <span>{r.agent_count} 个 Agent</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 关系图 */}
              {graph && graph.nodes.length > 0 && (
                <div className="bg-white border border-gray-200 rounded-xl p-5">
                  <div className="text-sm font-semibold mb-3">复用关系图</div>
                  <div className="flex flex-wrap gap-2">
                    {graph.nodes.map((n: any) => (
                      <div key={n.id}
                        className={`px-3 py-2 rounded-lg text-xs border-2 ${
                          n.type === 'source' ? 'border-blue-400 bg-blue-50 font-bold'
                            : n.type === 'agent' ? 'border-green-300 bg-green-50'
                              : 'border-purple-300 bg-purple-50'
                        }`}>
                        <div className="font-medium">{n.name.slice(0, 16)}</div>
                        <div className="text-gray-400 mt-0.5">{n.type} ({n.mode})</div>
                      </div>
                    ))}
                  </div>
                  <div className="mt-3 text-xs text-gray-400">
                    边: {graph.edges.map((e: any) => `${e.label}(${e.status})`).join(', ')}
                  </div>
                </div>
              )}
            </>
          )}

          {!stats && <div className="text-center py-8 text-gray-400 text-sm">输入 Skill ID 查看复用统计</div>}
        </div>
      )}
    </div>
  )
}

export default SkillReusePage
