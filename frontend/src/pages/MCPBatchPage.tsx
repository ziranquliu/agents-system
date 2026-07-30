import React, { useEffect, useState, useCallback } from 'react'
import {
  createMCPBatchInstall, executeMCPBatch, listMCPBatchQueues,
  listMCPBindings, updateMCPBinding, removeMCPBinding,
  checkMCPUpdates, syncMCPBinding, syncAllMCPBindings,
  MCPAgentBinding,
} from '../api/mcpBatch'
import apiFetch from '../api/client'
import { useToast } from '../components/ui'

const MCPBatchPage: React.FC = () => {
  const toast = useToast()

  // 标签页
  const [tab, setTab] = useState<'install' | 'bindings' | 'sync'>('install')

  // 选项
  const [mcps, setMcps] = useState<any[]>([])
  const [agents, setAgents] = useState<any[]>([])
  const [selectedMcpIds, setSelectedMcpIds] = useState<string[]>([])
  const [selectedAgentIds, setSelectedAgentIds] = useState<string[]>([])
  const [syncMode, setSyncMode] = useState('shared')
  const [creating, setCreating] = useState(false)

  // 队列
  const [queues, setQueues] = useState<any[]>([])
  const [loadingQueues, setLoadingQueues] = useState(false)
  const [currentQueue, setCurrentQueue] = useState<any>(null)

  // 绑定
  const [bindings, setBindings] = useState<MCPAgentBinding[]>([])
  const [totalBindings, setTotalBindings] = useState(0)
  const [loadingBindings, setLoadingBindings] = useState(false)

  // 同步
  const [mcpId, setMcpId] = useState('')
  const [syncResult, setSyncResult] = useState<any[]>([])

  const loadOptions = async () => {
    try {
      const [mcpResp, agentResp] = await Promise.all([
        apiFetch('/api/v1/mcp-servers', { method: 'GET' }),
        apiFetch('/api/v1/agents', { method: 'GET' }),
      ])
      const mcpData = mcpResp.data?.data || mcpResp.data || []
      const agentData = agentResp.data?.data || agentResp.data || []
      setMcps(Array.isArray(mcpData) ? mcpData : [])
      setAgents(Array.isArray(agentData) ? agentData : [])
    } catch { toast.error('加载选项失败') }
  }

  const loadQueues = useCallback(async () => {
    setLoadingQueues(true)
    try {
      const result = await listMCPBatchQueues()
      setQueues(result.data || [])
    } catch { toast.error('加载失败') }
    finally { setLoadingQueues(false) }
  }, [toast])

  const loadBindings = useCallback(async () => {
    setLoadingBindings(true)
    try {
      const result = await listMCPBindings({ offset: 0, limit: 100 })
      setBindings(result.data || [])
      setTotalBindings(result.total || 0)
    } catch { toast.error('加载失败') }
    finally { setLoadingBindings(false) }
  }, [toast])

  useEffect(() => { loadOptions() }, [])
  useEffect(() => { if (tab === 'install') loadQueues() }, [tab])
  useEffect(() => { if (tab === 'bindings') loadBindings() }, [tab])

  const handleInstall = async () => {
    if (selectedMcpIds.length === 0 || selectedAgentIds.length === 0) {
      toast.error('请选择 MCP 和 Agent'); return
    }
    setCreating(true)
    try {
      const queue = await createMCPBatchInstall(selectedMcpIds, selectedAgentIds, syncMode)
      setCurrentQueue(queue)
      // 自动执行
      const result = await executeMCPBatch(queue.id)
      setCurrentQueue(result)
      toast.success(`安装完成: ${result.success_count} 成功, ${result.fail_count} 失败`)
      loadQueues()
    } catch { toast.error('安装失败') }
    finally { setCreating(false) }
  }

  const handleRemoveBinding = async (id: string) => {
    if (!confirm('解除绑定后该 Agent 将无法使用此 MCP，确认？')) return
    try {
      await removeMCPBinding(id)
      toast.success('已解除绑定')
      loadBindings()
    } catch { toast.error('删除失败') }
  }

  const handleUpdateSyncMode = async (id: string, syncMode: string) => {
    try {
      await updateMCPBinding(id, { sync_mode: syncMode })
      toast.success('同步模式已更新')
      loadBindings()
    } catch { toast.error('更新失败') }
  }

  const handleCheckUpdates = async () => {
    if (!mcpId.trim()) { toast.error('请输入 MCP ID'); return }
    try {
      const data = await checkMCPUpdates(mcpId)
      setSyncResult(data)
      if (data.length === 0) toast.success('没有需要同步的更新')
    } catch { toast.error('检查失败') }
  }

  const handleSyncAll = async () => {
    if (!mcpId.trim()) return
    try {
      const data = await syncAllMCPBindings(mcpId)
      toast.success(`已同步 ${data.total || data.length || 0} 个绑定`)
      setSyncResult([])
    } catch { toast.error('同步失败') }
  }

  const renderSyncModeBadge = (mode: string) => {
    const m: Record<string, [string, string]> = {
      shared: ['🔗 共享连接', 'bg-blue-100 text-blue-700'],
      independent: ['📋 独立连接', 'bg-green-100 text-green-700'],
      template: ['📐 模板化', 'bg-purple-100 text-purple-700'],
    }
    const [label, cls] = m[mode] || [mode, 'bg-gray-100']
    return <span className={`px-2 py-0.5 rounded text-xs font-medium ${cls}`}>{label}</span>
  }

  const renderStatusBadge = (status: string) => {
    const m: Record<string, [string, string]> = {
      active: ['✅ 正常', 'bg-green-100 text-green-700'],
      outdated: ['🔄 有更新', 'bg-yellow-100 text-yellow-700'],
      error: ['❌ 错误', 'bg-red-100 text-red-700'],
      syncing: ['🔄 同步中', 'bg-blue-100 text-blue-700'],
    }
    const [label, cls] = m[status] || [status, 'bg-gray-100']
    return <span className={`px-2 py-0.5 rounded text-xs font-medium ${cls}`}>{label}</span>
  }

  const toggleId = (setter: React.Dispatch<React.SetStateAction<string[]>>, id: string) => {
    setter(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id])
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold flex items-center gap-2">🔌 MCP 批量安装与跨 Agent 同步</h1>
        <p className="text-gray-500 mt-1">批量注册 · 三种同步模式 · 敏感加密</p>
      </div>

      <div className="flex gap-1 mb-6 border-b">
        {[
          { key: 'install', label: '📦 批量安装' },
          { key: 'bindings', label: '🔗 绑定管理' },
          { key: 'sync', label: '🔄 同步管理' },
        ].map(t => (
          <button key={t.key} onClick={() => setTab(t.key as any)}
            className={`px-4 py-2 text-sm border-b-2 ${tab === t.key ? 'border-blue-500 text-blue-600 font-medium' : 'border-transparent text-gray-500'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* 批量安装 */}
      {tab === 'install' && (
        <div className="space-y-4">
          <div className="bg-white border border-gray-200 rounded-xl p-5">
            <h3 className="font-semibold mb-4">新建批量安装</h3>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium mb-1">选择 MCP ({selectedMcpIds.length})</label>
                <div className="max-h-48 overflow-y-auto border rounded-lg divide-y">
                  {mcps.map((m: any) => (
                    <label key={m.id} className="flex items-center px-3 py-2 hover:bg-gray-50 cursor-pointer text-sm">
                      <input type="checkbox" checked={selectedMcpIds.includes(m.id)} onChange={() => toggleId(setSelectedMcpIds, m.id)} className="mr-2" />
                      {m.name || m.id.slice(0, 12)}
                    </label>
                  ))}
                  {mcps.length === 0 && <div className="text-center py-4 text-xs text-gray-400">暂无 MCP</div>}
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">选择目标 Agent ({selectedAgentIds.length})</label>
                <div className="max-h-48 overflow-y-auto border rounded-lg divide-y">
                  {agents.map((a: any) => (
                    <label key={a.id} className="flex items-center px-3 py-2 hover:bg-gray-50 cursor-pointer text-sm">
                      <input type="checkbox" checked={selectedAgentIds.includes(a.id)} onChange={() => toggleId(setSelectedAgentIds, a.id)} className="mr-2" />
                      {a.name || a.id.slice(0, 12)}
                    </label>
                  ))}
                  {agents.length === 0 && <div className="text-center py-4 text-xs text-gray-400">暂无 Agent</div>}
                </div>
              </div>
            </div>

            <div className="mb-4">
              <label className="block text-sm font-medium mb-1">同步模式</label>
              <div className="flex gap-3">
                {[
                  { value: 'shared', label: '🔗 共享连接', desc: '所有 Agent 共享同一个 MCP 连接' },
                  { value: 'independent', label: '📋 独立连接', desc: '每个 Agent 拥有独立的 MCP 副本' },
                  { value: 'template', label: '📐 模板化', desc: '从源 MCP 派生，可自定义覆盖' },
                ].map(m => (
                  <div key={m.value} onClick={() => setSyncMode(m.value)}
                    className={`flex-1 border-2 rounded-xl p-3 cursor-pointer ${syncMode === m.value ? 'border-blue-300 bg-blue-50' : 'border-gray-200'}`}>
                    <div className="text-sm font-medium">{m.label}</div>
                    <div className="text-xs text-gray-500 mt-1">{m.desc}</div>
                  </div>
                ))}
              </div>
            </div>

            <button onClick={handleInstall} disabled={creating || selectedMcpIds.length === 0 || selectedAgentIds.length === 0}
              className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50">
              {creating ? '安装中...' : `安装 ${selectedMcpIds.length} MCP × ${selectedAgentIds.length} Agent`}
            </button>
          </div>

          {currentQueue && (
            <div className={`rounded-xl p-4 ${currentQueue.status === 'completed' ? 'bg-green-50 border border-green-200' : 'bg-blue-50 border border-blue-200'}`}>
              <div className="flex items-center gap-2 mb-1">
                <span>{currentQueue.status === 'completed' ? '✅' : '🔄'}</span>
                <span className="font-medium">安装结果</span>
              </div>
              <div className="flex gap-4 text-sm">
                <span>总 {currentQueue.total_items}</span>
                <span className="text-green-600">✓ {currentQueue.success_count}</span>
                <span className="text-red-600">✗ {currentQueue.fail_count}</span>
              </div>
            </div>
          )}

          <div className="bg-white border border-gray-200 rounded-xl">
            <div className="px-5 py-3 border-b bg-gray-50 text-sm font-semibold">安装历史</div>
            {loadingQueues ? (
              <div className="flex justify-center py-8"><div className="animate-spin w-5 h-5 border-2 border-blue-600 border-t-transparent rounded-full" /></div>
            ) : queues.length === 0 ? (
              <div className="text-center py-8 text-gray-400 text-sm">暂无记录</div>
            ) : (
              <div className="divide-y text-sm">
                {queues.map((q: any) => (
                  <div key={q.id} className="px-5 py-3 flex justify-between">
                    <div>
                      <span className="font-mono text-xs">{q.id.slice(0, 12)}...</span>
                      <span className="mx-2">{renderStatusBadge(q.status)}</span>
                      <span className="text-xs text-gray-500">{q.created_at ? new Date(q.created_at).toLocaleString() : ''}</span>
                    </div>
                    <span className="text-xs text-gray-500">✓{q.success_count} ✗{q.fail_count}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* 绑定管理 */}
      {tab === 'bindings' && (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="px-5 py-3 border-b bg-gray-50 text-sm font-semibold">MCP-Agent 绑定 ({totalBindings})</div>
          {loadingBindings ? (
            <div className="flex justify-center py-12"><div className="animate-spin w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full" /></div>
          ) : bindings.length === 0 ? (
            <div className="text-center py-12 text-gray-400 text-sm">暂无绑定关系</div>
          ) : (
            <div className="divide-y">
              {bindings.map(b => (
                <div key={b.id} className="px-5 py-4 text-sm">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        {renderSyncModeBadge(b.sync_mode)}
                        {renderStatusBadge(b.status)}
                        {b.is_encrypted && <span className="px-1.5 py-0.5 bg-red-100 text-red-600 rounded text-xs">🔒 加密</span>}
                      </div>
                      <div className="flex items-center gap-2 mt-1">
                        <code className="text-xs bg-gray-100 px-1 py-0.5">{b.mcp_server_name || b.mcp_server_id.slice(0, 12)}</code>
                        <span className="text-gray-400">→</span>
                        <code className="text-xs bg-gray-100 px-1 py-0.5">{b.agent_name || b.agent_id.slice(0, 12)}</code>
                      </div>
                      <div className="text-xs text-gray-400 mt-1">
                        v{b.synced_version || '-'}
                        {b.last_synced_at && <> · 同步: {new Date(b.last_synced_at).toLocaleString()}</>}
                        {b.sync_error && <span className="text-red-500 ml-2">错误: {b.sync_error}</span>}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <select value={b.sync_mode} onChange={e => handleUpdateSyncMode(b.id, e.target.value)}
                        className="px-2 py-1 border rounded text-xs">
                        <option value="shared">共享</option>
                        <option value="independent">独立</option>
                        <option value="template">模板</option>
                      </select>
                      <button onClick={() => handleRemoveBinding(b.id)}
                        className="px-2 py-1 text-xs text-red-500 hover:bg-red-50 rounded">解除</button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 同步管理 */}
      {tab === 'sync' && (
        <div className="space-y-4">
          <div className="bg-white border border-gray-200 rounded-xl p-5">
            <div className="flex items-end gap-3 mb-4">
              <div className="flex-1 max-w-md">
                <label className="block text-sm font-medium mb-1">MCP Server ID</label>
                <input type="text" value={mcpId} onChange={e => setMcpId(e.target.value)}
                  placeholder="输入 MCP Server ID" className="w-full px-3 py-2 border rounded-lg text-sm" />
              </div>
              <button onClick={handleCheckUpdates} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm">检查更新</button>
              {syncResult.length > 0 && (
                <button onClick={handleSyncAll} className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm">同步全部 ({syncResult.length})</button>
              )}
            </div>

            {syncResult.length > 0 ? (
              <div className="border border-yellow-200 rounded-lg divide-y">
                <div className="px-4 py-2 bg-yellow-50 text-xs text-yellow-700">检测到 {syncResult.length} 个需要同步的绑定</div>
                {syncResult.map((r: any) => (
                  <div key={r.binding_id} className="px-4 py-3 flex items-center justify-between text-sm">
                    <div>
                      <code className="text-xs">{r.agent_id?.slice(0, 12)}...</code>
                      <span className="text-gray-400 mx-2">v{r.current_version || '-'} → v{r.new_version || '-'}</span>
                      {renderSyncModeBadge(r.sync_mode)}
                    </div>
                    <button onClick={() => syncMCPBinding(r.binding_id).then(() => { toast.success('同步完成'); handleCheckUpdates() })}
                      className="px-3 py-1 text-xs bg-blue-100 text-blue-700 rounded">同步</button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-400 text-sm">输入 MCP Server ID 检查更新</div>
            )}
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-xs text-blue-700">
            <strong>💡 同步模式说明：</strong>
            <ul className="mt-1 list-disc ml-4 space-y-0.5">
              <li><strong>共享连接 (shared)</strong>：所有 Agent 共享同一个 MCP 连接配置，源更新即时生效</li>
              <li><strong>独立连接 (independent)</strong>：每个 Agent 拥有独立副本，同步时复制源配置</li>
              <li><strong>模板化 (template)</strong>：从源 MCP 派生，可配置参数覆盖项</li>
              <li>敏感配置（API Key 等）可通过 <strong>AES-256</strong> 加密存储</li>
            </ul>
          </div>
        </div>
      )}
    </div>
  )
}

export default MCPBatchPage
