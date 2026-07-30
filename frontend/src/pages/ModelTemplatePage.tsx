import React, { useEffect, useState, useCallback } from 'react'
import {
  getTemplateDetail, listTemplateVersions, createTemplateVersion, rollbackTemplate,
  bindAgentToTemplate, unbindAgentFromTemplate, updateBinding,
  syncTemplateToAgents, rollbackBindings,
  TemplateDetail, ModelTemplateVersion,
} from '../api/modelTemplates'
import apiFetch from '../api/client'
import { useToast } from '../components/ui'

const ModelTemplatePage: React.FC = () => {
  const toast = useToast()
  const [tab, setTab] = useState<'list' | 'detail'>('list')

  // 模板列表
  const [templates, setTemplates] = useState<any[]>([])
  const [loadingTemplates, setLoadingTemplates] = useState(false)

  // 选中的模板
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<TemplateDetail | null>(null)
  const [detailTab, setDetailTab] = useState<'bindings' | 'versions' | 'sync'>('bindings')
  const [loadingDetail, setLoadingDetail] = useState(false)

  // 绑定弹窗
  const [showBind, setShowBind] = useState(false)
  const [bindForm, setBindForm] = useState({ agent_id: '', sync_mode: 'auto', gray_percentage: '100' })

  // 版本
  const [versions, setVersions] = useState<ModelTemplateVersion[]>([])

  // 同步
  const [syncing, setSyncing] = useState(false)

  const loadTemplates = useCallback(async () => {
    setLoadingTemplates(true)
    try {
      const resp = await apiFetch('/api/v1/models/templates', { method: 'GET' })
      setTemplates(Array.isArray(resp.data) ? resp.data : (resp.data?.data || []))
    } catch {
      toast.error('加载模板列表失败')
    } finally {
      setLoadingTemplates(false)
    }
  }, [toast])

  useEffect(() => { loadTemplates() }, [])

  const loadDetail = async (id: string) => {
    setSelectedId(id)
    setTab('detail')
    setLoadingDetail(true)
    try {
      const data = await getTemplateDetail(id)
      setDetail(data)
      // Load versions
      const verResp = await listTemplateVersions(id)
      setVersions(verResp.data || [])
    } catch {
      toast.error('加载模板详情失败')
    } finally {
      setLoadingDetail(false)
    }
  }

  const handleCreateVersion = async () => {
    if (!selectedId) return
    try {
      const v = await createTemplateVersion(selectedId, '手动创建快照')
      toast.success(`版本 ${v.version} 已创建`)
      const verResp = await listTemplateVersions(selectedId)
      setVersions(verResp.data || [])
      loadDetail(selectedId)
    } catch {
      toast.error('创建版本失败')
    }
  }

  const handleRollback = async (versionId: string) => {
    if (!selectedId || !confirm('回滚将恢复模板配置到目标版本，是否继续？')) return
    try {
      await rollbackTemplate(selectedId, versionId)
      toast.success('回滚成功')
      loadDetail(selectedId)
    } catch {
      toast.error('回滚失败')
    }
  }

  const handleBind = async () => {
    if (!selectedId || !bindForm.agent_id.trim()) { toast.error('请输入 Agent ID'); return }
    try {
      await bindAgentToTemplate(selectedId, bindForm.agent_id.trim(), {}, bindForm.sync_mode, parseInt(bindForm.gray_percentage) || 100)
      toast.success('绑定成功')
      setShowBind(false)
      setBindForm({ agent_id: '', sync_mode: 'auto', gray_percentage: '100' })
      loadDetail(selectedId)
    } catch {
      toast.error('绑定失败')
    }
  }

  const handleUnbind = async (agentId: string) => {
    if (!selectedId || !confirm('解除绑定后，智能体将不再接收模板更新。确定？')) return
    try {
      await unbindAgentFromTemplate(selectedId, agentId)
      toast.success('已解除绑定')
      loadDetail(selectedId)
    } catch {
      toast.error('解除绑定失败')
    }
  }

  const handleUpdateSyncMode = async (bindingId: string, syncMode: string) => {
    try {
      await updateBinding(bindingId, { sync_mode: syncMode })
      toast.success('同步模式已更新')
      loadDetail(selectedId!)
    } catch {
      toast.error('更新失败')
    }
  }

  const handleSync = async (forceAll = false) => {
    if (!selectedId) return
    setSyncing(true)
    try {
      const res = await syncTemplateToAgents(selectedId, forceAll)
      toast.success(`同步完成: ${res.synced} 成功, ${res.skipped} 跳过, ${res.failed} 失败`)
      loadDetail(selectedId)
    } catch {
      toast.error('同步失败')
    } finally {
      setSyncing(false)
    }
  }

  const handleRollbackBindings = async (versionId: string) => {
    if (!selectedId) return
    const version = versions.find(v => v.id === versionId)
    if (!version || !confirm(`将所有绑定回滚到版本 ${version.version}？`)) return
    try {
      const res = await rollbackBindings(selectedId, version.version)
      toast.success(`已回滚 ${res.rolled_back} 个绑定`)
      loadDetail(selectedId)
    } catch {
      toast.error('回滚失败')
    }
  }

  const renderStatusBadge = (status: string) => {
    const m: Record<string, [string, string]> = {
      synced: ['✅ 已同步', 'text-green-600 bg-green-50'],
      pending: ['⏳ 待同步', 'text-yellow-600 bg-yellow-50'],
      syncing: ['🔄 同步中', 'text-blue-600 bg-blue-50'],
      failed: ['❌ 失败', 'text-red-600 bg-red-50'],
      rolled_back: ['↩️ 已回滚', 'text-gray-600 bg-gray-50'],
    }
    const [label, cls] = m[status] || [status, 'text-gray-500']
    return <span className={`px-2 py-0.5 rounded text-xs font-medium ${cls}`}>{label}</span>
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold flex items-center gap-2">⚙️ 模型配置模板与一键复用</h1>
        <p className="text-gray-500 mt-1">版本管理 · 绑定复用 · 灰度同步</p>
      </div>

      {tab === 'list' && (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="px-5 py-3 border-b bg-gray-50 flex items-center justify-between">
            <span className="font-semibold">模型配置模板列表 ({templates.length})</span>
            <span className="text-xs text-gray-400">点击模板查看详情 → 版本/绑定/同步管理</span>
          </div>
          {loadingTemplates ? (
            <div className="flex justify-center py-12"><div className="animate-spin w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full" /></div>
          ) : templates.length === 0 ? (
            <div className="text-center py-12 text-gray-400">暂无模板 — 请先在「模型市场」或「模型配置」页面创建模板</div>
          ) : (
            <div className="divide-y">
              {templates.map((t: any) => (
                <div key={t.id} onClick={() => loadDetail(t.id)}
                  className="px-5 py-4 cursor-pointer hover:bg-gray-50 transition-colors">
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="font-medium">{t.name || '未命名模板'}</h3>
                      <div className="flex items-center gap-3 mt-1 text-sm text-gray-500">
                        <span>{t.provider} / {t.model}</span>
                        {t.is_default && <span className="px-1.5 py-0.5 bg-blue-100 text-blue-600 rounded text-xs font-medium">默认</span>}
                      </div>
                      {t.description && <p className="text-xs text-gray-400 mt-1">{t.description}</p>}
                    </div>
                    <span className="text-xs text-gray-400">创建于 {t.created_at ? new Date(t.created_at).toLocaleDateString() : '-'}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === 'detail' && (
        <div className="space-y-4">
          {/* 返回按钮 */}
          <button onClick={() => { setTab('list'); setSelectedId(null); setDetail(null) }}
            className="text-sm text-blue-600 hover:underline">← 返回列表</button>

          {loadingDetail ? (
            <div className="flex justify-center py-12"><div className="animate-spin w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full" /></div>
          ) : detail ? (
            <>
              {/* 模板概要 */}
              <div className="bg-white border border-gray-200 rounded-xl p-5">
                <div className="flex items-start justify-between">
                  <div>
                    <h2 className="text-xl font-bold">{detail.name}</h2>
                    <div className="flex items-center gap-3 mt-1">
                      <span className="text-sm text-gray-500">{detail.provider} / {detail.model}</span>
                      {detail.is_default && <span className="px-2 py-0.5 bg-blue-100 text-blue-600 rounded text-xs font-medium">默认模板</span>}
                    </div>
                    {detail.description && <p className="text-sm text-gray-400 mt-2">{detail.description}</p>}
                  </div>
                  <div className="flex gap-3 text-sm items-center">
                    <div className="text-center px-3 py-1 bg-blue-50 rounded-lg">
                      <div className="text-lg font-bold text-blue-600">{detail.version_count}</div>
                      <div className="text-xs text-blue-500">版本</div>
                    </div>
                    <div className="text-center px-3 py-1 bg-purple-50 rounded-lg">
                      <div className="text-lg font-bold text-purple-600">{detail.binding_count}</div>
                      <div className="text-xs text-purple-500">绑定</div>
                    </div>
                  </div>
                </div>

                {/* 配置预览 */}
                <div className="mt-4 bg-gray-50 rounded-lg p-3">
                  <div className="text-xs text-gray-500 mb-1">当前配置</div>
                  <pre className="text-xs text-gray-600 overflow-x-auto">{JSON.stringify(detail.config, null, 2) ?? ''}</pre>
                </div>

                {detail.config.temperature ? (
                  <div className="flex items-center gap-4 mt-3 text-sm">
                    <span>Temperature: <strong>{String(detail.config.temperature)}</strong></span>
                    <span>Max Tokens: <strong>{detail.config.max_tokens ? String(detail.config.max_tokens) : '-'}</strong></span>
                    <span>Context Window: <strong>{detail.config.context_window ? String(detail.config.context_window) : '-'}</strong></span>
                  </div>
                ) : null}
              </div>

              {/* 子标签页 */}
              <div className="flex gap-1 mb-2">
                {[
                  { key: 'bindings', label: `🔗 绑定管理 (${detail.binding_count})` },
                  { key: 'versions', label: `📋 版本历史 (${detail.version_count})` },
                  { key: 'sync', label: '🔄 同步管理' },
                ].map(t => (
                  <button key={t.key} onClick={() => setDetailTab(t.key as any)}
                    className={`px-4 py-2 text-sm border-b-2 ${detailTab === t.key ? 'border-blue-500 text-blue-600 font-medium' : 'border-transparent text-gray-500'}`}>
                    {t.label}
                  </button>
                ))}
              </div>

              {/* 绑定管理 */}
              {detailTab === 'bindings' && (
                <div className="bg-white border border-gray-200 rounded-xl">
                  <div className="px-5 py-3 border-b bg-gray-50 flex items-center justify-between">
                    <span className="font-semibold text-sm">绑定的智能体</span>
                    <button onClick={() => setShowBind(true)}
                      className="px-3 py-1 bg-blue-600 text-white rounded-lg text-xs hover:bg-blue-700">+ 绑定智能体</button>
                  </div>
                  {detail.bindings.length === 0 ? (
                    <div className="text-center py-12 text-gray-400 text-sm">暂无绑定 — 点击上方按钮绑定智能体</div>
                  ) : (
                    <div className="divide-y">
                      {detail.bindings.map(b => (
                        <div key={b.id} className="px-5 py-4">
                          <div className="flex items-start justify-between">
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="font-mono text-sm font-medium">{b.agent_id}</span>
                                {renderStatusBadge(b.gray_status)}
                              </div>
                              <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
                                <span>模式:
                                  <select value={b.sync_mode} onChange={e => handleUpdateSyncMode(b.id, e.target.value)}
                                    className="ml-1 px-1 py-0.5 border rounded text-xs">
                                    <option value="auto">自动同步</option>
                                    <option value="manual">手动同步</option>
                                    <option value="gray">灰度同步</option>
                                  </select>
                                </span>
                                {b.sync_mode === 'gray' && <span>灰度比例: {b.gray_percentage}%</span>}
                                {b.gray_synced_version && <span>已同步至: v{b.gray_synced_version}</span>}
                              </div>
                              {b.last_synced_at && <div className="text-xs text-gray-400 mt-0.5">最后同步: {new Date(b.last_synced_at).toLocaleString()}</div>}
                              {b.gray_error && <div className="text-xs text-red-500 mt-0.5">错误: {b.gray_error}</div>}
                              {Object.keys(b.override_config).length > 0 && (
                                <div className="mt-2 bg-yellow-50 rounded p-2 text-xs">
                                  <span className="font-medium text-yellow-700">参数覆盖: </span>
                                  <code className="text-yellow-600">{JSON.stringify(b.override_config) ?? ''}</code>
                                </div>
                              )}
                            </div>
                            <button onClick={() => handleUnbind(b.agent_id)}
                              className="px-2 py-1 text-xs text-red-500 hover:bg-red-50 rounded">解除</button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* 版本历史 */}
              {detailTab === 'versions' && (
                <div className="bg-white border border-gray-200 rounded-xl">
                  <div className="px-5 py-3 border-b bg-gray-50 flex items-center justify-between">
                    <span className="font-semibold text-sm">版本历史</span>
                    <button onClick={handleCreateVersion}
                      className="px-3 py-1 bg-blue-600 text-white rounded-lg text-xs hover:bg-blue-700">+ 创建快照</button>
                  </div>
                  {versions.length === 0 ? (
                    <div className="text-center py-12 text-gray-400 text-sm">暂无版本记录</div>
                  ) : (
                    <div className="divide-y">
                      {versions.map(v => (
                        <div key={v.id} className="px-5 py-4">
                          <div className="flex items-start justify-between">
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs font-bold">v{v.version}</span>
                                <span className="text-sm font-medium">{v.name}</span>
                                {v.change_log && <span className="text-xs text-gray-400">— {v.change_log}</span>}
                              </div>
                              <div className="text-xs text-gray-500 mt-1">
                                {v.provider} / {v.model} · 创建于 {v.created_at ? new Date(v.created_at).toLocaleString() : '-'}
                              </div>
                              <pre className="mt-2 bg-gray-50 rounded p-2 text-xs text-gray-600 max-h-24 overflow-auto">
                                {JSON.stringify(v.config, null, 2) ?? ''}
                              </pre>
                            </div>
                            <div className="flex gap-1">
                              <button onClick={() => handleRollback(v.id)}
                                className="px-2 py-1 text-xs border rounded hover:bg-yellow-50">回滚到此</button>
                              <button onClick={() => handleRollbackBindings(v.id)}
                                className="px-2 py-1 text-xs border rounded hover:bg-purple-50">绑定回滚</button>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* 同步管理 */}
              {detailTab === 'sync' && (
                <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4">
                  <h3 className="font-semibold">同步操作</h3>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="border border-gray-200 rounded-xl p-4">
                      <div className="text-2xl mb-2">🚀</div>
                      <h4 className="font-medium text-sm mb-1">增量同步</h4>
                      <p className="text-xs text-gray-400 mb-3">将模板当前配置同步到所有绑定的智能体<br/>灰度模式将按比例随机执行</p>
                      <button onClick={() => handleSync(false)} disabled={syncing}
                        className="w-full px-3 py-1.5 bg-blue-600 text-white rounded-lg text-xs hover:bg-blue-700 disabled:opacity-50">
                        {syncing ? '同步中...' : '执行同步'}
                      </button>
                    </div>
                    <div className="border border-gray-200 rounded-xl p-4">
                      <div className="text-2xl mb-2">📡</div>
                      <h4 className="font-medium text-sm mb-1">强制全量同步</h4>
                      <p className="text-xs text-gray-400 mb-3">忽略灰度比例，对所有绑定执行同步<br/>适用于紧急配置更新</p>
                      <button onClick={() => handleSync(true)} disabled={syncing}
                        className="w-full px-3 py-1.5 bg-orange-500 text-white rounded-lg text-xs hover:bg-orange-600 disabled:opacity-50">
                        {syncing ? '同步中...' : '全量同步'}
                      </button>
                    </div>
                    <div className="border border-gray-200 rounded-xl p-4">
                      <div className="text-2xl mb-2">↩️</div>
                      <h4 className="font-medium text-sm mb-1">绑定回滚</h4>
                      <p className="text-xs text-gray-400 mb-3">将所有绑定的配置回滚到指定历史版本</p>
                      <select onChange={e => e.target.value && handleRollbackBindings(e.target.value)}
                        className="w-full px-3 py-1.5 border rounded-lg text-xs">
                        <option value="">选择目标版本...</option>
                        {versions.map(v => <option key={v.id} value={v.id}>v{v.version} — {v.change_log || v.name}</option>)}
                      </select>
                    </div>
                  </div>

                  <div className="bg-gray-50 rounded-lg p-4 text-xs text-gray-500 space-y-1">
                    <p><strong>同步模式说明：</strong></p>
                    <p>• <strong>自动同步 (auto)</strong>：每次模板更新自动推送到所有绑定的智能体</p>
                    <p>• <strong>手动同步 (manual)</strong>：需要手动点击「执行同步」才会触发推送</p>
                    <p>• <strong>灰度同步 (gray)</strong>：按设定百分比随机选取智能体推送，适合逐步验证</p>
                    <p className="mt-2 text-yellow-600">⚠ 每次同步前会自动将当前配置保存为版本快照</p>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="text-center py-12 text-gray-400">模板加载失败</div>
          )}
        </div>
      )}

      {/* 绑定弹窗 */}
      {showBind && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setShowBind(false)}>
          <div className="bg-white rounded-2xl w-full max-w-md m-4 p-6" onClick={e => e.stopPropagation()}>
            <h2 className="text-lg font-bold mb-4">绑定智能体</h2>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium mb-1">智能体 ID *</label>
                <input type="text" value={bindForm.agent_id} onChange={e => setBindForm(f => ({ ...f, agent_id: e.target.value }))}
                  placeholder="输入 Agent ID" className="w-full px-3 py-2 border rounded-lg text-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">同步模式</label>
                <select value={bindForm.sync_mode} onChange={e => setBindForm(f => ({ ...f, sync_mode: e.target.value }))}
                  className="w-full px-3 py-2 border rounded-lg text-sm">
                  <option value="auto">🔄 自动同步 — 模板更新时自动推送</option>
                  <option value="manual">✋ 手动同步 — 需手动触发推送</option>
                  <option value="gray">📊 灰度同步 — 按百分比灰度推送</option>
                </select>
              </div>
              {bindForm.sync_mode === 'gray' && (
                <div>
                  <label className="block text-sm font-medium mb-1">灰度比例 (%)</label>
                  <input type="number" min={1} max={100} value={bindForm.gray_percentage}
                    onChange={e => setBindForm(f => ({ ...f, gray_percentage: e.target.value }))}
                    className="w-full px-3 py-2 border rounded-lg text-sm" />
                  <p className="text-xs text-gray-400 mt-0.5">每次同步时，此比例的智能体会接收到更新</p>
                </div>
              )}
            </div>
            <div className="flex gap-3 justify-end mt-6">
              <button onClick={() => setShowBind(false)} className="px-4 py-2 border rounded-lg text-sm">取消</button>
              <button onClick={handleBind} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm">绑定</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ModelTemplatePage
