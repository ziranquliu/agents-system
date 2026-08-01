import React, { useEffect, useState, useCallback } from 'react'
import {
  createIntervention, listInterventions, approveIntervention, rejectIntervention,
  createRating, listRatings, getRatingStats, recordRatingSnapshot,
  getConversationCsvUrl, getConversationPdfUrl, listExportableConversations,
  batchExportConversations, BatchExportParams,
  HumanIntervention, DialogueRating,
} from '../api/dialogueEnhancement'
import { useToast } from '../components/ui'

const DialogueEnhancementPage: React.FC = () => {
  const toast = useToast()

  // 标签
  const [tab, setTab] = useState<'interventions' | 'ratings' | 'export' | 'stats'>('interventions')

  // HITL
  const [interventions, setInterventions] = useState<HumanIntervention[]>([])
  const [loadingInv, setLoadingInv] = useState(false)
  const [showCreateInv, setShowCreateInv] = useState(false)
  const [invForm, setInvForm] = useState({ conversation_id: '', agent_id: '', intervention_type: 'review', original_content: '' })

  // Ratings
  const [ratings, setRatings] = useState<DialogueRating[]>([])
  const [loadingRatings, setLoadingRatings] = useState(false)
  const [showCreateRating, setShowCreateRating] = useState(false)
  const [ratingForm, setRatingForm] = useState({
    conversation_id: '', satisfaction_score: 0,
    relevance_score: 0, accuracy_score: 0, completeness_score: 0,
    clarity_score: 0, feedback_text: '', feedback_category: 'neutral',
  })

  // Stats
  const [stats, setStats] = useState<Record<string, unknown> | null>(null)

  // Export
  const [conversations, setConversations] = useState<any[]>([])
  const [loadingConv, setLoadingConv] = useState(false)

  // 批量导出
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [batchFormat, setBatchFormat] = useState<'csv' | 'json' | 'html'>('csv')
  const [batchIncludeMeta, setBatchIncludeMeta] = useState(true)
  const [batchMask, setBatchMask] = useState(true)
  const [exportingBatch, setExportingBatch] = useState(false)

  // 批量选择
  const toggleSelect = (id: string) => {
    setSelectedIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id])
  }
  const toggleSelectAll = () => {
    if (selectedIds.length === conversations.length) setSelectedIds([])
    else setSelectedIds(conversations.map(c => c.id))
  }
  // 切换标签时清空选择
  const switchTab = (key: string) => {
    setSelectedIds([])
    setTab(key as any)
  }

  const loadInterventions = useCallback(async () => {
    setLoadingInv(true)
    try { const r = await listInterventions({ offset: 0, limit: 50 }); setInterventions(r.data || []); setTotalInv(r.total) }
    catch { toast.error('加载失败') }
    finally { setLoadingInv(false) }
  }, [toast])
  const [totalInv, setTotalInv] = useState(0)

  const loadRatings = useCallback(async () => {
    setLoadingRatings(true)
    try { const r = await listRatings({ offset: 0, limit: 50 }); setRatings(r.data || []) }
    catch { toast.error('加载失败') }
    finally { setLoadingRatings(false) }
  }, [toast])

  const loadStats = async () => {
    try { const r = await getRatingStats(); setStats(r) }
    catch { toast.error('加载统计失败') }
  }

  const loadConversations = useCallback(async () => {
    setLoadingConv(true)
    try { const r = await listExportableConversations({ offset: 0, limit: 50 }); setConversations(r.data || []) }
    catch { toast.error('加载失败') }
    finally { setLoadingConv(false) }
  }, [toast])

  useEffect(() => { if (tab === 'interventions') loadInterventions() }, [tab])
  useEffect(() => { if (tab === 'ratings') loadRatings() }, [tab])
  useEffect(() => { if (tab === 'stats') loadStats() }, [tab])
  useEffect(() => { if (tab === 'export') { loadConversations(); setSelectedIds([]) } }, [tab])

  const handleBatchExport = async () => {
    if (selectedIds.length === 0) { toast.error('请先勾选要导出的对话'); return }
    setExportingBatch(true)
    try {
      const params: BatchExportParams = {
        conversation_ids: selectedIds,
        format: batchFormat,
        include_metadata: batchIncludeMeta,
        mask_sensitive: batchMask,
      }
      await batchExportConversations(params)
      toast.success(`已导出 ${selectedIds.length} 个对话`)
    } catch {
      toast.error('批量导出失败')
    } finally {
      setExportingBatch(false)
    }
  }

  const handleCreateInv = async () => {
    if (!invForm.conversation_id || !invForm.agent_id) { toast.error('请填写必要信息'); return }
    try {
      await createIntervention(invForm)
      toast.success('介入请求已创建')
      setShowCreateInv(false)
      setInvForm({ conversation_id: '', agent_id: '', intervention_type: 'review', original_content: '' })
      loadInterventions()
    } catch { toast.error('创建失败') }
  }

  const handleApprove = async (id: string) => {
    try { await approveIntervention(id); toast.success('已批准'); loadInterventions() }
    catch { toast.error('操作失败') }
  }

  const handleReject = async (id: string) => {
    try { await rejectIntervention(id); toast.success('已驳回'); loadInterventions() }
    catch { toast.error('操作失败') }
  }

  const handleCreateRating = async () => {
    if (!ratingForm.conversation_id) { toast.error('请选择对话'); return }
    try {
      await createRating(ratingForm)
      toast.success('评分已提交')
      setShowCreateRating(false)
      setRatingForm({ conversation_id: '', satisfaction_score: 0, relevance_score: 0, accuracy_score: 0, completeness_score: 0, clarity_score: 0, feedback_text: '', feedback_category: 'neutral' })
      loadRatings()
    } catch { toast.error('提交失败') }
  }

  const renderStatusBadge = (status: string) => {
    const m: Record<string, [string, string]> = {
      pending: ['⏳ 待处理', 'text-yellow-600 bg-yellow-50'],
      approved: ['✅ 已批准', 'text-green-600 bg-green-50'],
      rejected: ['❌ 已驳回', 'text-red-600 bg-red-50'],
      modified: ['✏️ 已修改', 'text-blue-600 bg-blue-50'],
    }
    const [label, cls] = m[status] || [status, 'text-gray-500']
    return <span className={`px-2 py-0.5 rounded text-xs font-medium ${cls}`}>{label}</span>
  }

  const renderScore = (v: number | null | undefined) => v ? <span className="font-bold text-blue-600">{v}</span> : <span className="text-gray-300">-</span>

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">💬 对话与交互增强</h1>
        <p className="text-gray-500 mt-1">Human-in-the-loop · 质量评分 · 高级导出</p>
      </div>

      <div className="flex gap-1 mb-6 border-b">
        {[
          { key: 'interventions', label: `👤 人工介入 (${totalInv})` },
          { key: 'ratings', label: '⭐ 评分管理' },
          { key: 'stats', label: '📊 满意度分析' },
          { key: 'export', label: '📤 导出管理' },
        ].map(t => (
          <button key={t.key} onClick={() => switchTab(t.key)}
            className={`px-4 py-2 text-sm border-b-2 ${tab === t.key ? 'border-blue-500 text-blue-600 font-medium' : 'border-transparent text-gray-500'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* HITL */}
      {tab === 'interventions' && (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="px-5 py-3 border-b bg-gray-50 flex items-center justify-between">
            <span className="font-semibold text-sm">人工介入记录</span>
            <button onClick={() => setShowCreateInv(true)} className="px-3 py-1 bg-blue-600 text-white rounded-lg text-xs">+ 新建介入</button>
          </div>
          {loadingInv ? (
            <div className="flex justify-center py-12"><div className="animate-spin w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full" /></div>
          ) : interventions.length === 0 ? (
            <div className="text-center py-12 text-gray-400 text-sm">暂无介入记录</div>
          ) : (
            <div className="divide-y">
              {interventions.map(inv => (
                <div key={inv.id} className="px-5 py-4 text-sm">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        {renderStatusBadge(inv.status)}
                        <span className="px-2 py-0.5 bg-gray-100 rounded text-xs">{inv.intervention_type}</span>
                        <span className="text-xs text-gray-400">Agent: {inv.agent_id.slice(0, 12)}...</span>
                      </div>
                      <div className="mt-1 text-xs text-gray-500">
                        <span>对话: {inv.conversation_id.slice(0, 12)}...</span>
                        {inv.handled_by && <span className="ml-3">处理人: {inv.handled_by}</span>}
                        <span className="ml-3">{inv.created_at ? new Date(inv.created_at).toLocaleString() : ''}</span>
                      </div>
                      <div className="mt-2 bg-gray-50 rounded p-2 text-xs max-h-16 overflow-hidden">{inv.original_content?.slice(0, 200)}</div>
                      {inv.approval_note && <div className="mt-1 text-xs text-gray-400">备注: {inv.approval_note}</div>}
                    </div>
                    {inv.status === 'pending' && (
                      <div className="flex gap-1 ml-3">
                        <button onClick={() => handleApprove(inv.id)} className="px-2 py-1 text-xs bg-green-100 text-green-700 rounded">批准</button>
                        <button onClick={() => handleReject(inv.id)} className="px-2 py-1 text-xs bg-red-100 text-red-700 rounded">驳回</button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Ratings */}
      {tab === 'ratings' && (
        <div className="space-y-4">
          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
            <div className="px-5 py-3 border-b bg-gray-50 flex items-center justify-between">
              <span className="font-semibold text-sm">对话评分</span>
              <button onClick={() => setShowCreateRating(true)} className="px-3 py-1 bg-blue-600 text-white rounded-lg text-xs">+ 新建评分</button>
            </div>
            {loadingRatings ? (
              <div className="flex justify-center py-12"><div className="animate-spin w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full" /></div>
            ) : ratings.length === 0 ? (
              <div className="text-center py-12 text-gray-400 text-sm">暂无评分</div>
            ) : (
              <div className="divide-y">
                {ratings.map(r => (
                  <div key={r.id} className="px-5 py-3 text-sm">
                    <div className="flex items-center gap-3">
                      <span>综合: <strong className="text-blue-600">{r.overall_score ?? '-'}</strong></span>
                      <span className="text-gray-400">|</span>
                      <span>满意度: {renderScore(r.satisfaction_score)}/5</span>
                      <span className="text-gray-400">|</span>
                      <span>相关: {renderScore(r.relevance_score)}</span>
                      <span>准确: {renderScore(r.accuracy_score)}</span>
                      <span>完整: {renderScore(r.completeness_score)}</span>
                      <span className={`px-1.5 py-0.5 rounded text-xs ${r.feedback_category === 'positive' ? 'bg-green-100 text-green-700' : r.feedback_category === 'negative' ? 'bg-red-100 text-red-700' : 'bg-gray-100'}`}>{r.feedback_category}</span>
                    </div>
                    {r.feedback_text && <div className="text-xs text-gray-500 mt-1">反馈: {r.feedback_text}</div>}
                    <div className="text-xs text-gray-400 mt-0.5">对话: {r.conversation_id.slice(0, 12)}... | {r.rated_by_type} | {r.created_at ? new Date(r.created_at).toLocaleString() : ''}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Stats */}
      {tab === 'stats' && (
        <div className="space-y-4">
          <div className="flex gap-2">
            <button onClick={loadStats} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm">刷新统计</button>
            <button onClick={async () => { await recordRatingSnapshot(); toast.success('快照已记录') }}
              className="px-4 py-2 border rounded-lg text-sm">记录快照</button>
          </div>

          {stats ? (
            <div className="space-y-4">
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                {[
                  { label: '总评分', value: String(stats.total_ratings ?? 0), color: 'bg-blue-50 text-blue-700' },
                  { label: '综合均分', value: String(stats.avg_overall ?? '-'), color: 'bg-purple-50 text-purple-700' },
                  { label: '满意度均分', value: String(stats.avg_satisfaction ?? '-'), color: 'bg-green-50 text-green-700' },
                  { label: '相关性均分', value: String(stats.avg_relevance ?? '-'), color: 'bg-indigo-50 text-indigo-700' },
                ].map(c => (
                  <div key={c.label} className={`rounded-xl p-4 ${c.color}`}>
                    <div className="text-xs opacity-70">{c.label}</div>
                    <div className="text-2xl font-bold mt-1">{c.value}</div>
                  </div>
                ))}
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="bg-white border border-gray-200 rounded-xl p-5">
                  <h3 className="font-semibold text-sm mb-3">各维度均分</h3>
                  <div className="space-y-2">
                    {[
                      { label: '相关性', value: stats.avg_relevance as number },
                      { label: '准确性', value: stats.avg_accuracy as number },
                      { label: '完整性', value: stats.avg_completeness as number },
                      { label: '清晰度', value: stats.avg_clarity as number },
                      { label: '响应速度', value: stats.avg_speed as number },
                    ].map(d => (
                      <div key={d.label} className="flex items-center gap-2">
                        <span className="text-xs w-16">{d.label}</span>
                        <div className="flex-1 h-3 bg-gray-100 rounded-sm overflow-hidden">
                          <div className="h-full bg-blue-500 rounded-sm" style={{ width: `${(d.value || 0) * 10}%` }} />
                        </div>
                        <span className="text-xs text-gray-500 w-8">{d.value?.toFixed(1) ?? '-'}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="bg-white border border-gray-200 rounded-xl p-5">
                  <h3 className="font-semibold text-sm mb-3">满意度分布</h3>
                  {Object.keys(stats.satisfaction_distribution as Record<string, number> || {}).length > 0 ? (
                    <div className="space-y-2">
                      {Object.entries(stats.satisfaction_distribution as Record<string, number>).map(([k, v]) => {
                        const total = Object.values(stats.satisfaction_distribution as Record<string, number>).reduce((a, b) => a + b, 0)
                        return (
                          <div key={k} className="flex items-center gap-2">
                            <span className="text-xs w-10">{k} 分</span>
                            <div className="flex-1 h-3 bg-gray-100 rounded-sm overflow-hidden">
                              <div className={`h-full rounded-sm ${parseInt(k) >= 4 ? 'bg-green-500' : parseInt(k) >= 3 ? 'bg-yellow-500' : 'bg-red-500'}`}
                                style={{ width: `${total > 0 ? (v / total * 100) : 0}%` }} />
                            </div>
                            <span className="text-xs text-gray-500 w-8">{v}</span>
                          </div>
                        )
                      })}
                    </div>
                  ) : <p className="text-xs text-gray-400">暂无数据</p>}
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-12 text-gray-400 text-sm">点击刷新加载统计</div>
          )}
        </div>
      )}

      {/* Export */}
      {tab === 'export' && (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="px-5 py-3 border-b bg-gray-50 flex items-center justify-between">
            <span className="text-sm font-semibold">导出对话</span>
            <span className="text-xs text-gray-500">已选 {selectedIds.length} 个</span>
          </div>

          {/* 批量导出区域 */}
          {conversations.length > 0 && (
            <div className="px-5 py-4 border-b bg-blue-50/40">
              <div className="flex flex-wrap items-center gap-3">
                <button onClick={handleBatchExport} disabled={exportingBatch || selectedIds.length === 0}
                  className={`px-4 py-2 rounded-lg text-sm font-medium ${exportingBatch || selectedIds.length === 0
                    ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                    : 'bg-blue-600 text-white hover:bg-blue-700'}`}>
                  {exportingBatch ? '导出中…' : `📦 批量下载 (${selectedIds.length})`}
                </button>
                <select value={batchFormat} onChange={e => setBatchFormat(e.target.value as any)}
                  className="px-3 py-2 border rounded-lg text-sm bg-white">
                  <option value="csv">CSV（统计摘要）</option>
                  <option value="json">JSON（结构化）</option>
                  <option value="html">HTML（报告）</option>
                </select>
                <label className="flex items-center gap-1.5 text-sm text-gray-600 cursor-pointer">
                  <input type="checkbox" checked={batchIncludeMeta} onChange={e => setBatchIncludeMeta(e.target.checked)}
                    className="w-4 h-4 accent-blue-600" /> 含元数据
                </label>
                <label className="flex items-center gap-1.5 text-sm text-gray-600 cursor-pointer">
                  <input type="checkbox" checked={batchMask} onChange={e => setBatchMask(e.target.checked)}
                    className="w-4 h-4 accent-blue-600" /> 隐私脱敏
                </label>
              </div>
              <p className="text-xs text-gray-400 mt-2">勾选下方对话后批量导出；单次最多 50 个，支持跨 Agent 多选。</p>
            </div>
          )}

          {loadingConv ? (
            <div className="flex justify-center py-12"><div className="animate-spin w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full" /></div>
          ) : conversations.length === 0 ? (
            <div className="text-center py-12 text-gray-400 text-sm">暂无可导出的对话</div>
          ) : (
            <div className="divide-y">
              <div className="px-5 py-2 bg-gray-50 flex items-center gap-3 text-xs text-gray-500">
                <label className="flex items-center gap-1.5 cursor-pointer">
                  <input type="checkbox" checked={selectedIds.length > 0 && selectedIds.length === conversations.length}
                    onChange={toggleSelectAll} className="w-4 h-4 accent-blue-600" />
                  全选
                </label>
              </div>
              {conversations.map(c => (
                <div key={c.id} className={`px-5 py-4 flex items-center justify-between text-sm ${selectedIds.includes(c.id) ? 'bg-blue-50/60' : ''}`}>
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    <input type="checkbox" checked={selectedIds.includes(c.id)} onChange={() => toggleSelect(c.id)}
                      className="w-4 h-4 accent-blue-600 shrink-0" />
                    <div className="min-w-0">
                      <div className="font-medium truncate">{c.title || '无标题对话'}</div>
                      <div className="text-xs text-gray-500 mt-0.5">
                        {c.message_count} 条消息 · Agent: {c.agent_id?.slice(0, 12)}... · {c.created_at ? new Date(c.created_at).toLocaleDateString() : ''}
                      </div>
                    </div>
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <a href={getConversationCsvUrl(c.id)} target="_blank" rel="noopener noreferrer"
                      className="px-3 py-1 text-xs border rounded hover:bg-gray-50">📥 CSV</a>
                    <a href={getConversationPdfUrl(c.id)} target="_blank" rel="noopener noreferrer"
                      className="px-3 py-1 text-xs border rounded hover:bg-gray-50">📄 HTML</a>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 创建介入弹窗 */}
      {showCreateInv && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setShowCreateInv(false)}>
          <div className="bg-white rounded-2xl w-full max-w-lg m-4 p-6" onClick={e => e.stopPropagation()}>
            <h2 className="text-lg font-bold mb-4">新建人工介入</h2>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium mb-1">对话 ID *</label>
                <input value={invForm.conversation_id} onChange={e => setInvForm(f => ({ ...f, conversation_id: e.target.value }))}
                  className="w-full px-3 py-2 border rounded-lg text-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Agent ID *</label>
                <input value={invForm.agent_id} onChange={e => setInvForm(f => ({ ...f, agent_id: e.target.value }))}
                  className="w-full px-3 py-2 border rounded-lg text-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">介入类型</label>
                <select value={invForm.intervention_type} onChange={e => setInvForm(f => ({ ...f, intervention_type: e.target.value }))}
                  className="w-full px-3 py-2 border rounded-lg text-sm">
                  <option value="review">审核 (review)</option>
                  <option value="approve">审批 (approve)</option>
                  <option value="reject">驳回 (reject)</option>
                  <option value="modify">修改 (modify)</option>
                  <option value="override">覆盖 (override)</option>
                  <option value="pause">暂停 (pause)</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">原始内容</label>
                <textarea value={invForm.original_content} onChange={e => setInvForm(f => ({ ...f, original_content: e.target.value }))}
                  rows={4} className="w-full px-3 py-2 border rounded-lg text-sm" />
              </div>
            </div>
            <div className="flex gap-3 justify-end mt-6">
              <button onClick={() => setShowCreateInv(false)} className="px-4 py-2 border rounded-lg text-sm">取消</button>
              <button onClick={handleCreateInv} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm">创建</button>
            </div>
          </div>
        </div>
      )}

      {/* 创建评分弹窗 */}
      {showCreateRating && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setShowCreateRating(false)}>
          <div className="bg-white rounded-2xl w-full max-w-xl m-4 p-6" onClick={e => e.stopPropagation()}>
            <h2 className="text-lg font-bold mb-4">新建评分</h2>
            <div className="space-y-3 max-h-[70vh] overflow-y-auto pr-2">
              <div>
                <label className="block text-sm font-medium mb-1">对话 ID *</label>
                <input value={ratingForm.conversation_id} onChange={e => setRatingForm(f => ({ ...f, conversation_id: e.target.value }))}
                  className="w-full px-3 py-2 border rounded-lg text-sm" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium mb-1">满意度 (1-5)</label>
                  <div className="flex gap-1">
                    {[1, 2, 3, 4, 5].map(s => (
                      <button key={s} onClick={() => setRatingForm(f => ({ ...f, satisfaction_score: s }))}
                        className={`w-8 h-8 rounded-full text-sm ${ratingForm.satisfaction_score === s ? 'bg-yellow-400 text-white' : 'bg-gray-100'}`}>{s}</button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">反馈类别</label>
                  <select value={ratingForm.feedback_category} onChange={e => setRatingForm(f => ({ ...f, feedback_category: e.target.value }))}
                    className="w-full px-3 py-2 border rounded-lg text-sm">
                    <option value="positive">好评</option>
                    <option value="negative">差评</option>
                    <option value="neutral">中性</option>
                    <option value="bug_report">Bug 报告</option>
                    <option value="feature_request">功能建议</option>
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3">
                {[
                  { key: 'relevance_score', label: '相关性 (1-10)' },
                  { key: 'accuracy_score', label: '准确性 (1-10)' },
                  { key: 'completeness_score', label: '完整性 (1-10)' },
                  { key: 'clarity_score', label: '清晰度 (1-10)' },
                  { key: 'speed_score', label: '响应速度 (1-10)' },
                ].map(d => (
                  <div key={d.key}>
                    <label className="block text-xs font-medium mb-1">{d.label}</label>
                    <select value={(ratingForm as any)[d.key]} onChange={e => setRatingForm(f => ({ ...f, [d.key]: parseInt(e.target.value) }))}
                      className="w-full px-2 py-1.5 border rounded-lg text-xs">
                      <option value={0}>-</option>
                      {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(n => <option key={n} value={n}>{n}</option>)}
                    </select>
                  </div>
                ))}
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">反馈内容</label>
                <textarea value={ratingForm.feedback_text} onChange={e => setRatingForm(f => ({ ...f, feedback_text: e.target.value }))}
                  rows={3} className="w-full px-3 py-2 border rounded-lg text-sm" />
              </div>
            </div>
            <div className="flex gap-3 justify-end mt-6">
              <button onClick={() => setShowCreateRating(false)} className="px-4 py-2 border rounded-lg text-sm">取消</button>
              <button onClick={handleCreateRating} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm">提交评分</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default DialogueEnhancementPage
