import React, { useEffect, useState, useCallback } from 'react'
import {
  listMemories, getMemory, createMemory, updateMemory, deleteMemory,
  batchForget, mergeDuplicates, processExpired,
  getMemoryStats, recordSnapshot,
  AgentMemory, MemoryStats, ListMemoriesParams,
} from '../api/memory'
import { useToast } from '../components/ui'

const MEMORY_TYPES = [
  { value: '', label: '全部类型' },
  { value: 'short_term', label: '🟢 短期记忆' },
  { value: 'long_term', label: '🔵 长期记忆' },
  { value: 'shared', label: '🟣 共享记忆' },
]

const CATEGORIES = [
  { value: '', label: '全部类别' },
  { value: 'conversation', label: '💬 对话' },
  { value: 'knowledge', label: '📖 知识' },
  { value: 'preference', label: '❤️ 偏好' },
  { value: 'behavior', label: '🔄 行为' },
  { value: 'custom', label: '📌 自定义' },
]

const importanceBand = (s: number) => {
  if (s >= 7) return 2
  if (s >= 4) return 1
  return 0
}

const AgentMemoryPage: React.FC = () => {
  const toast = useToast()

  // 标签页
  const [tab, setTab] = useState<'list' | 'detail' | 'stats' | 'manage'>('list')

  // 列表
  const [memories, setMemories] = useState<AgentMemory[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [filters, setFilters] = useState<ListMemoriesParams>({
    memory_type: '',
    category: '',
    keyword: '',
    sort_by: 'created_at',
    sort_desc: true,
    offset: 0,
    limit: 20,
  })

  // 详情
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<AgentMemory | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  // 统计
  const [stats, setStats] = useState<MemoryStats | null>(null)
  const [statsLoading, setStatsLoading] = useState(false)
  const [statsAgentId, setStatsAgentId] = useState('agent-1')

  // 管理
  const [manageAgentId, setManageAgentId] = useState('agent-1')
  const [processing, setProcessing] = useState(false)

  // 创建
  const [showCreate, setShowCreate] = useState(false)
  const [createForm, setCreateForm] = useState({
    agent_id: 'agent-1',
    title: '',
    content: '',
    memory_type: 'long_term',
    category: 'conversation',
    tags: '',
    is_public: false,
    ttl_seconds: '',
  })

  // 编辑
  const [editId, setEditId] = useState<string | null>(null)
  const [editForm, setEditForm] = useState({ title: '', content: '', summary: '', tags: '', category: 'conversation' })

  const loadMemories = useCallback(async () => {
    setLoading(true)
    try {
      const clean: ListMemoriesParams = {}
      Object.entries(filters).forEach(([k, v]) => {
        if (v !== '' && v !== undefined && v !== null && v !== false) clean[k as keyof ListMemoriesParams] = v as any
      })
      if (clean.memory_type === '') delete clean.memory_type
      if (clean.category === '') delete clean.category
      const data = await listMemories(clean)
      setMemories(data.data)
      setTotal(data.total)
    } catch {
      toast.error('加载记忆列表失败')
    } finally {
      setLoading(false)
    }
  }, [filters, toast])

  useEffect(() => {
    if (tab === 'list' || tab === 'detail') loadMemories()
  }, [tab])

  const loadDetail = async (id: string) => {
    setSelectedId(id)
    setDetailLoading(true)
    setTab('detail')
    try {
      const data = await getMemory(id)
      setDetail(data)
    } catch { toast.error('加载记忆详情失败') }
    finally { setDetailLoading(false) }
  }

  const loadStats = async () => {
    if (!statsAgentId) return
    setStatsLoading(true)
    try {
      const data = await getMemoryStats(statsAgentId)
      setStats(data)
    } catch { toast.error('加载统计失败') }
    finally { setStatsLoading(false) }
  }

  useEffect(() => {
    if (tab === 'stats') loadStats()
  }, [tab, statsAgentId])

  const handleCreate = async () => {
    if (!createForm.content.trim()) { toast.error('请输入记忆内容'); return }
    try {
      const tags = createForm.tags ? JSON.stringify(createForm.tags.split(',').map(t => t.trim()).filter(Boolean)) : '[]'
      const ttl = createForm.ttl_seconds ? parseInt(createForm.ttl_seconds) : undefined
      await createMemory({
        agent_id: createForm.agent_id,
        title: createForm.title,
        content: createForm.content,
        memory_type: createForm.memory_type,
        category: createForm.category,
        tags,
        is_public: createForm.is_public,
        ...(ttl ? { ttl_seconds: ttl } : {}),
      })
      toast.success('记忆已创建')
      setShowCreate(false)
      setCreateForm({ agent_id: 'agent-1', title: '', content: '', memory_type: 'long_term', category: 'conversation', tags: '', is_public: false, ttl_seconds: '' })
      loadMemories()
    } catch { toast.error('创建记忆失败') }
  }

  const handleDelete = async (id: string) => {
    try {
      await deleteMemory(id)
      toast.success('记忆已遗忘')
      if (selectedId === id) { setSelectedId(null); setDetail(null) }
      loadMemories()
    } catch { toast.error('操作失败') }
  }

  const handleEdit = (mem: AgentMemory) => {
    setEditId(mem.id)
    setEditForm({
      title: mem.title || '',
      content: mem.content || '',
      summary: mem.summary || '',
      tags: mem.tags ? (typeof mem.tags === 'string' ? mem.tags : JSON.stringify(mem.tags)) : '',
      category: mem.category || 'conversation',
    })
  }

  const handleSaveEdit = async () => {
    if (!editId) return
    try {
      const data: Record<string, unknown> = { title: editForm.title, content: editForm.content, summary: editForm.summary, category: editForm.category }
      if (editForm.tags) data['tags'] = editForm.tags.split(',').map(t => t.trim()).filter(Boolean)
      await updateMemory(editId, data)
      toast.success('记忆已更新')
      setEditId(null)
      if (selectedId) loadDetail(selectedId)
      loadMemories()
    } catch { toast.error('更新失败') }
  }

  const handleProcessExpired = async () => {
    setProcessing(true)
    try {
      const data = await processExpired()
      toast.success(`处理完成: ${data.expired_count} 过期 + ${data.low_importance_count} 低重要性`)
      loadMemories()
    } catch { toast.error('处理失败') }
    finally { setProcessing(false) }
  }

  const handleBatchForget = async () => {
    setProcessing(true)
    try {
      const data = await batchForget(manageAgentId)
      toast.success(`已遗忘 ${data.forgotten_count} 条记忆`)
      loadMemories()
    } catch { toast.error('操作失败') }
    finally { setProcessing(false) }
  }

  const handleMerge = async () => {
    setProcessing(true)
    try {
      const data = await mergeDuplicates(manageAgentId)
      toast.success(`合并了 ${data.merged_count} 条重复记忆`)
      loadMemories()
    } catch { toast.error('操作失败') }
    finally { setProcessing(false) }
  }

  const handleRecordSnapshot = async () => {
    try {
      await recordSnapshot(statsAgentId)
      toast.success('分析快照已记录')
    } catch { toast.error('记录失败') }
  }

  const renderImportanceBar = (score: number) => {
    const band = importanceBand(score)
    const colors = ['bg-gray-400', 'bg-blue-500', 'bg-red-500']
    const pct = Math.min(100, (score / 10) * 100)
    return (
      <div className="flex items-center gap-2">
        <div className="w-16 h-1.5 bg-gray-200 rounded-full overflow-hidden">
          <div className={`h-full ${colors[band]} rounded-full transition-all`} style={{ width: `${pct}%` }} />
        </div>
        <span className="text-xs text-gray-500 w-8">{score.toFixed(1)}</span>
      </div>
    )
  }

  const renderTypeBadge = (t: string) => {
    const m = { short_term: ['🟢 短期', 'bg-green-100 text-green-700'], long_term: ['🔵 长期', 'bg-blue-100 text-blue-700'], shared: ['🟣 共享', 'bg-purple-100 text-purple-700'] }
    const [label, cls] = m[t as keyof typeof m] || [t, 'bg-gray-100 text-gray-700']
    return <span className={`px-2 py-0.5 rounded text-xs font-medium ${cls}`}>{label}</span>
  }

  const renderCategoryBadge = (c: string) => {
    const emojis: Record<string, string> = { conversation: '💬', knowledge: '📖', preference: '❤️', behavior: '🔄', custom: '📌' }
    return <span className="text-xs text-gray-500">{emojis[c] || c} {c}</span>
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">🧠 智能体记忆管理</h1>
          <p className="text-gray-500 mt-1">三层记忆体系 — 短期 / 长期 / 共享</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShowCreate(true)} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm">新建记忆</button>
        </div>
      </div>

      {/* 标签页导航 */}
      <div className="flex gap-1 mb-6 border-b">
        {[
          { key: 'list', label: '📋 记忆列表' },
          { key: 'detail', label: '📄 记忆详情' },
          { key: 'stats', label: '📊 统计分析' },
          { key: 'manage', label: '⚙️ 遗忘管理' },
        ].map(t => (
          <button key={t.key} onClick={() => { setTab(t.key as any); if (t.key === 'detail' && !selectedId && memories.length > 0) loadDetail(memories[0].id) }}
            className={`px-4 py-2 text-sm border-b-2 transition-colors ${tab === t.key ? 'border-blue-500 text-blue-600 font-medium' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* ==================== 标签页1: 列表 ==================== */}
      {tab === 'list' && (
        <div className="space-y-4">
          {/* 过滤栏 */}
          <div className="bg-white border border-gray-200 rounded-xl p-4">
            <div className="flex flex-wrap gap-3 items-end">
              <div>
                <label className="block text-xs text-gray-500 mb-1">记忆层级</label>
                <select value={filters.memory_type || ''} onChange={e => setFilters(f => ({ ...f, memory_type: e.target.value, offset: 0 }))}
                  className="px-3 py-1.5 border rounded-lg text-sm">
                  {MEMORY_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">类别</label>
                <select value={filters.category || ''} onChange={e => setFilters(f => ({ ...f, category: e.target.value, offset: 0 }))}
                  className="px-3 py-1.5 border rounded-lg text-sm">
                  {CATEGORIES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </div>
              <div className="flex-1 min-w-[200px]">
                <label className="block text-xs text-gray-500 mb-1">关键词搜索</label>
                <input type="text" value={filters.keyword || ''} onChange={e => setFilters(f => ({ ...f, keyword: e.target.value, offset: 0 }))}
                  onKeyDown={e => e.key === 'Enter' && loadMemories()}
                  placeholder="搜索内容和标题..." className="w-full px-3 py-1.5 border rounded-lg text-sm" />
              </div>
              <button onClick={loadMemories} className="px-4 py-1.5 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">搜索</button>
            </div>
          </div>

          {/* 列表 */}
          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b bg-gray-50 flex items-center justify-between">
              <span className="font-semibold text-sm">记忆列表 ({total})</span>
              <span className="text-xs text-gray-400">点击查看详情</span>
            </div>
            {loading ? (
              <div className="flex justify-center py-12"><div className="animate-spin w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full" /></div>
            ) : memories.length === 0 ? (
              <div className="text-center py-12 text-gray-400 text-sm">暂无记忆</div>
            ) : (
              <div className="divide-y">
                {memories.map(m => (
                  <div key={m.id} onClick={() => loadDetail(m.id)}
                    className={`px-5 py-4 cursor-pointer hover:bg-gray-50 transition-colors ${selectedId === m.id ? 'bg-blue-50' : ''}`}>
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          {renderTypeBadge(m.memory_type)}
                          {renderCategoryBadge(m.category)}
                          {m.is_sensitive && <span className="px-1.5 py-0.5 bg-red-100 text-red-600 rounded text-xs font-medium">🔒 敏感</span>}
                          {m.is_public && <span className="px-1.5 py-0.5 bg-purple-100 text-purple-600 rounded text-xs font-medium">🌍 公开</span>}
                        </div>
                        <h3 className="font-medium text-sm truncate">{m.title || '(无标题)'}</h3>
                        <p className="text-xs text-gray-500 mt-0.5 line-clamp-1">{m.content?.slice(0, 150)}</p>
                        <div className="flex items-center gap-3 mt-1.5 text-xs text-gray-400">
                          <span>Agent: {m.agent_id}</span>
                          <span>访问 {m.access_count} 次</span>
                          <span>{renderImportanceBar(m.importance_score)}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-1 ml-3">
                        <button onClick={e => { e.stopPropagation(); handleEdit(m) }} className="p-1 text-gray-400 hover:text-blue-500" title="编辑">✏️</button>
                        <button onClick={e => { e.stopPropagation(); handleDelete(m.id) }} className="p-1 text-gray-400 hover:text-red-500" title="遗忘">🗑️</button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
            {/* 分页 */}
            {total > 20 && (
              <div className="px-5 py-3 border-t bg-gray-50 flex justify-between items-center text-sm">
                <span className="text-gray-500">共 {total} 条</span>
                <div className="flex gap-1">
                  <button disabled={(filters.offset ?? 0) === 0} onClick={() => setFilters(f => ({ ...f, offset: Math.max(0, (f.offset ?? 0) - (f.limit ?? 20)) }))}
                    className="px-3 py-1 border rounded text-xs disabled:opacity-30">上一页</button>
                  <span className="px-3 py-1 text-xs text-gray-500">第 {Math.floor((filters.offset ?? 0) / (filters.limit ?? 20)) + 1} / {Math.ceil(total / (filters.limit ?? 20))} 页</span>
                  <button disabled={(filters.offset ?? 0) + (filters.limit ?? 20) >= total} onClick={() => setFilters(f => ({ ...f, offset: (f.offset ?? 0) + (f.limit ?? 20) }))}
                    className="px-3 py-1 border rounded text-xs disabled:opacity-30">下一页</button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ==================== 标签页2: 详情 ==================== */}
      {tab === 'detail' && (
        <div className="bg-white border border-gray-200 rounded-xl">
          {!selectedId && !detail ? (
            <div className="text-center py-16 text-gray-400">请从列表中选择一条记忆查看详情</div>
          ) : detailLoading ? (
            <div className="flex justify-center py-16"><div className="animate-spin w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full" /></div>
          ) : detail ? (
            <div className="p-6 space-y-5">
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-lg font-bold">{detail.title || '(无标题)'}</h2>
                  <div className="flex gap-2 mt-1">
                    {renderTypeBadge(detail.memory_type)}
                    {renderCategoryBadge(detail.category)}
                    {detail.is_sensitive && <span className="px-2 py-0.5 bg-red-100 text-red-600 rounded text-xs font-medium">🔒 {detail.sensitive_info_type || '敏感信息'}</span>}
                  </div>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => handleEdit(detail)} className="px-3 py-1.5 border rounded-lg text-xs hover:bg-gray-50">编辑</button>
                  <button onClick={() => handleDelete(detail.id)} className="px-3 py-1.5 border border-red-200 text-red-500 rounded-lg text-xs hover:bg-red-50">遗忘</button>
                </div>
              </div>

              {/* 内容 */}
              <div>
                <h3 className="text-sm font-semibold text-gray-500 mb-2">记忆内容</h3>
                <div className="bg-gray-50 rounded-lg p-4 text-sm whitespace-pre-wrap">{detail.content}</div>
                {detail.masked_content && (
                  <div className="mt-2">
                    <h4 className="text-xs font-medium text-red-500 mb-1">🔒 脱敏版本</h4>
                    <div className="bg-red-50 rounded-lg p-3 text-sm text-red-700">{detail.masked_content}</div>
                  </div>
                )}
              </div>

              {detail.summary && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-500 mb-1">AI 摘要</h3>
                  <p className="text-sm text-gray-600 bg-yellow-50 rounded-lg p-3">{detail.summary}</p>
                </div>
              )}

              {/* 元数据 */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="bg-gray-50 rounded-lg p-3">
                  <div className="text-xs text-gray-400">重要性评分</div>
                  <div className="text-xl font-bold mt-0.5">{detail.importance_score.toFixed(1)} / 10</div>
                  {renderImportanceBar(detail.importance_score)}
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <div className="text-xs text-gray-400">访问次数</div>
                  <div className="text-xl font-bold mt-0.5">{detail.access_count}</div>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <div className="text-xs text-gray-400">Agent ID</div>
                  <div className="text-sm font-mono mt-0.5 truncate">{detail.agent_id}</div>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <div className="text-xs text-gray-400">来源</div>
                  <div className="text-sm mt-0.5">{detail.source_type || 'manual'}</div>
                </div>
              </div>

              {/* 标签 */}
              {detail.tags && detail.tags !== '[]' && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-500 mb-1">标签</h3>
                  <div className="flex flex-wrap gap-1">
                    {(JSON.parse(typeof detail.tags === 'string' ? detail.tags : '[]') as string[]).map((t, i) => (
                      <span key={i} className="px-2 py-0.5 bg-blue-50 text-blue-600 rounded text-xs">{t}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* 时间线 */}
              <div className="text-xs text-gray-400 border-t pt-3 grid grid-cols-2 gap-2">
                <div>创建时间: {detail.created_at ? new Date(detail.created_at).toLocaleString() : '-'}</div>
                <div>更新时间: {detail.updated_at ? new Date(detail.updated_at).toLocaleString() : '-'}</div>
                {detail.expires_at && <div>过期时间: {new Date(detail.expires_at).toLocaleString()}</div>}
                {detail.last_accessed_at && <div>最后访问: {new Date(detail.last_accessed_at).toLocaleString()}</div>}
                {detail.forgotten_at && <div>遗忘时间: {new Date(detail.forgotten_at).toLocaleString()} ({detail.forget_reason})</div>}
              </div>
            </div>
          ) : (
            <div className="text-center py-16 text-gray-400">请从列表中选择一条记忆查看详情</div>
          )}
        </div>
      )}

      {/* ==================== 标签页3: 统计 ==================== */}
      {tab === 'stats' && (
        <div className="space-y-4">
          <div className="bg-white border border-gray-200 rounded-xl p-4">
            <div className="flex items-end gap-3">
              <div className="flex-1 max-w-xs">
                <label className="block text-xs text-gray-500 mb-1">智能体 ID</label>
                <input type="text" value={statsAgentId} onChange={e => setStatsAgentId(e.target.value)}
                  className="w-full px-3 py-1.5 border rounded-lg text-sm" />
              </div>
              <button onClick={loadStats} className="px-4 py-1.5 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">刷新统计</button>
              <button onClick={handleRecordSnapshot} className="px-4 py-1.5 border rounded-lg text-sm hover:bg-gray-50">记录快照</button>
            </div>
          </div>

          {statsLoading ? (
            <div className="flex justify-center py-12"><div className="animate-spin w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full" /></div>
          ) : stats ? (
            <div className="space-y-4">
              {/* 概览卡片 */}
              <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
                {[
                  { label: '总记忆', value: stats.total_memories, color: 'bg-blue-50 text-blue-700' },
                  { label: '短期记忆', value: stats.short_term_count, color: 'bg-green-50 text-green-700' },
                  { label: '长期记忆', value: stats.long_term_count, color: 'bg-blue-50 text-blue-700' },
                  { label: '共享记忆', value: stats.shared_count, color: 'bg-purple-50 text-purple-700' },
                  { label: '遗忘记忆', value: stats.forgotten_count, color: 'bg-gray-100 text-gray-600' },
                ].map(c => (
                  <div key={c.label} className={`rounded-xl p-4 ${c.color}`}>
                    <div className="text-xs opacity-70">{c.label}</div>
                    <div className="text-2xl font-bold mt-1">{c.value}</div>
                  </div>
                ))}
              </div>

              {/* 详情 */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="bg-white border border-gray-200 rounded-xl p-5">
                  <h3 className="font-semibold text-sm mb-3">类别分布</h3>
                  {Object.keys(stats.category_distribution).length > 0 ? (
                    <div className="space-y-2">
                      {Object.entries(stats.category_distribution).map(([cat, count]) => {
                        const totalC = Object.values(stats.category_distribution).reduce((a, b) => a + b, 0)
                        const pct = totalC > 0 ? (count / totalC * 100).toFixed(1) : 0
                        return (
                          <div key={cat} className="flex items-center gap-2">
                            <span className="text-xs w-20">{renderCategoryBadge(cat)}</span>
                            <div className="flex-1 h-4 bg-gray-100 rounded-sm overflow-hidden">
                              <div className="h-full bg-blue-500 rounded-sm transition-all" style={{ width: `${pct}%` }} />
                            </div>
                            <span className="text-xs text-gray-500 w-10">{count}</span>
                            <span className="text-xs text-gray-400 w-10">{pct}%</span>
                          </div>
                        )
                      })}
                    </div>
                  ) : (
                    <p className="text-xs text-gray-400">暂无数据</p>
                  )}
                </div>

                <div className="bg-white border border-gray-200 rounded-xl p-5">
                  <h3 className="font-semibold text-sm mb-3">记忆质量指标</h3>
                  <div className="space-y-3">
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-500">平均重要性</span>
                      <span className="font-bold">{stats.avg_importance}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-500">敏感记忆数</span>
                      <span className="font-bold text-red-600">{stats.sensitive_count}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-500">TTL有效记忆</span>
                      <span className="font-bold">{stats.ttl_active_count}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-500">遗忘率</span>
                      <span className="font-bold">
                        {stats.total_memories + stats.forgotten_count > 0
                          ? ((stats.forgotten_count / (stats.total_memories + stats.forgotten_count)) * 100).toFixed(1) + '%'
                          : '0%'}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-12 text-gray-400 text-sm">输入 Agent ID 并点击刷新</div>
          )}
        </div>
      )}

      {/* ==================== 标签页4: 遗忘管理 ==================== */}
      {tab === 'manage' && (
        <div className="space-y-4">
          <div className="bg-white border border-gray-200 rounded-xl p-5">
            <div className="flex items-end gap-3 mb-5">
              <div className="flex-1 max-w-xs">
                <label className="block text-xs text-gray-500 mb-1">智能体 ID</label>
                <input type="text" value={manageAgentId} onChange={e => setManageAgentId(e.target.value)}
                  className="w-full px-3 py-1.5 border rounded-lg text-sm" />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="border border-gray-200 rounded-xl p-4 hover:shadow-sm transition-shadow">
                <div className="text-2xl mb-2">⏰</div>
                <h3 className="font-semibold text-sm mb-1">处理过期记忆</h3>
                <p className="text-xs text-gray-400 mb-3">自动处理 TTL 过期的短期记忆和低重要性长期记忆</p>
                <button onClick={handleProcessExpired} disabled={processing}
                  className="w-full px-3 py-1.5 bg-yellow-500 text-white rounded-lg text-xs hover:bg-yellow-600 disabled:opacity-50">
                  {processing ? '处理中...' : '立即处理'}
                </button>
              </div>

              <div className="border border-gray-200 rounded-xl p-4 hover:shadow-sm transition-shadow">
                <div className="text-2xl mb-2">🗑️</div>
                <h3 className="font-semibold text-sm mb-1">批量遗忘</h3>
                <p className="text-xs text-gray-400 mb-3">遗忘该智能体的所有记忆（可选按类型过滤）</p>
                <button onClick={handleBatchForget} disabled={processing}
                  className="w-full px-3 py-1.5 bg-red-500 text-white rounded-lg text-xs hover:bg-red-600 disabled:opacity-50">
                  {processing ? '处理中...' : '批量遗忘'}
                </button>
              </div>

              <div className="border border-gray-200 rounded-xl p-4 hover:shadow-sm transition-shadow">
                <div className="text-2xl mb-2">🔗</div>
                <h3 className="font-semibold text-sm mb-1">合并重复记忆</h3>
                <p className="text-xs text-gray-400 mb-3">检测并合并内容相似度 ≥80% 的长期记忆（保留重要）</p>
                <button onClick={handleMerge} disabled={processing}
                  className="w-full px-3 py-1.5 bg-blue-500 text-white rounded-lg text-xs hover:bg-blue-600 disabled:opacity-50">
                  {processing ? '处理中...' : '合并重复'}
                </button>
              </div>
            </div>
          </div>

          <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 text-xs text-yellow-700">
            <strong>⚠️ 注意：</strong> 遗忘操作不可逆（软删除可恢复，但批量操作会标记大量记忆）。建议先记录分析快照再执行。
          </div>
        </div>
      )}

      {/* ==================== 新建记忆弹窗 ==================== */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setShowCreate(false)}>
          <div className="bg-white rounded-2xl w-full max-w-lg m-4 p-6" onClick={e => e.stopPropagation()}>
            <h2 className="text-xl font-bold mb-4">新建记忆</h2>
            <div className="space-y-3 max-h-[70vh] overflow-y-auto pr-2">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium mb-1">记忆层级 *</label>
                  <select value={createForm.memory_type} onChange={e => setCreateForm(f => ({ ...f, memory_type: e.target.value }))}
                    className="w-full px-3 py-2 border rounded-lg text-sm">
                    <option value="short_term">🟢 短期记忆</option>
                    <option value="long_term">🔵 长期记忆</option>
                    <option value="shared">🟣 共享记忆</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">类别</label>
                  <select value={createForm.category} onChange={e => setCreateForm(f => ({ ...f, category: e.target.value }))}
                    className="w-full px-3 py-2 border rounded-lg text-sm">
                    <option value="conversation">💬 对话</option>
                    <option value="knowledge">📖 知识</option>
                    <option value="preference">❤️ 偏好</option>
                    <option value="behavior">🔄 行为</option>
                    <option value="custom">📌 自定义</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">智能体 ID *</label>
                <input type="text" value={createForm.agent_id} onChange={e => setCreateForm(f => ({ ...f, agent_id: e.target.value }))}
                  className="w-full px-3 py-2 border rounded-lg text-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">标题</label>
                <input type="text" value={createForm.title} onChange={e => setCreateForm(f => ({ ...f, title: e.target.value }))}
                  placeholder="记忆标题（可选）" className="w-full px-3 py-2 border rounded-lg text-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">内容 *</label>
                <textarea value={createForm.content} onChange={e => setCreateForm(f => ({ ...f, content: e.target.value }))}
                  rows={5} placeholder="输入记忆内容，将自动检测敏感信息并计算重要性..."
                  className="w-full px-3 py-2 border rounded-lg text-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">标签（逗号分隔）</label>
                <input type="text" value={createForm.tags} onChange={e => setCreateForm(f => ({ ...f, tags: e.target.value }))}
                  placeholder="标签1, 标签2, 标签3" className="w-full px-3 py-2 border rounded-lg text-sm" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium mb-1">TTL 秒（短期记忆）</label>
                  <input type="number" value={createForm.ttl_seconds} onChange={e => setCreateForm(f => ({ ...f, ttl_seconds: e.target.value }))}
                    placeholder="留空为永久" className="w-full px-3 py-2 border rounded-lg text-sm" />
                </div>
                <div className="flex items-end pb-2">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" checked={createForm.is_public} onChange={e => setCreateForm(f => ({ ...f, is_public: e.target.checked }))} />
                    <span className="text-sm">对所有智能体公开</span>
                  </label>
                </div>
              </div>
            </div>
            <div className="flex gap-3 justify-end mt-6">
              <button onClick={() => setShowCreate(false)} className="px-4 py-2 border rounded-lg text-sm">取消</button>
              <button onClick={handleCreate} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm">创建记忆</button>
            </div>
          </div>
        </div>
      )}

      {/* ==================== 编辑弹窗 ==================== */}
      {editId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setEditId(null)}>
          <div className="bg-white rounded-2xl w-full max-w-lg m-4 p-6" onClick={e => e.stopPropagation()}>
            <h2 className="text-xl font-bold mb-4">编辑记忆</h2>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium mb-1">标题</label>
                <input type="text" value={editForm.title} onChange={e => setEditForm(f => ({ ...f, title: e.target.value }))}
                  className="w-full px-3 py-2 border rounded-lg text-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">内容</label>
                <textarea value={editForm.content} onChange={e => setEditForm(f => ({ ...f, content: e.target.value }))}
                  rows={5} className="w-full px-3 py-2 border rounded-lg text-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">摘要</label>
                <input type="text" value={editForm.summary} onChange={e => setEditForm(f => ({ ...f, summary: e.target.value }))}
                  className="w-full px-3 py-2 border rounded-lg text-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">标签（逗号分隔）</label>
                <input type="text" value={editForm.tags} onChange={e => setEditForm(f => ({ ...f, tags: e.target.value }))}
                  className="w-full px-3 py-2 border rounded-lg text-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">类别</label>
                <select value={editForm.category} onChange={e => setEditForm(f => ({ ...f, category: e.target.value }))}
                  className="w-full px-3 py-2 border rounded-lg text-sm">
                  {CATEGORIES.filter(c => c.value !== '').map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </div>
            </div>
            <div className="flex gap-3 justify-end mt-6">
              <button onClick={() => setEditId(null)} className="px-4 py-2 border rounded-lg text-sm">取消</button>
              <button onClick={handleSaveEdit} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm">保存</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default AgentMemoryPage
