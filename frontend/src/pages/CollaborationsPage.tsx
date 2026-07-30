import React, { useEffect, useState } from 'react'
import {
  listCollaborations, createCollaboration, startCollaboration,
  getCollaborationTasks, listCollaborationModes,
  Collaboration, CollaborationTask, CollaborationMode,
} from '../api/collaborations'
import { listAgents, AgentInfo } from '../api/agents'
import { useToast } from '../components/ui'

const CollaborationsPage: React.FC = () => {
  const toast = useToast()
  const [items, setItems] = useState<Collaboration[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState<Collaboration | null>(null)
  const [tasks, setTasks] = useState<CollaborationTask[]>([])
  const [createOpen, setCreateOpen] = useState(false)
  const [detailOpen, setDetailOpen] = useState(false)
  const [modes, setModes] = useState<CollaborationMode[]>([])
  const [agents, setAgents] = useState<AgentInfo[]>([])

  // 创建表单
  const [formName, setFormName] = useState('')
  const [formDesc, setFormDesc] = useState('')
  const [formMode, setFormMode] = useState('sequential')
  const [formContext, setFormContext] = useState('')
  const [formTasks, setFormTasks] = useState<{ agent_id: string; role: string; input: string }[]>([{ agent_id: '', role: 'executor', input: '' }])
  const [creating, setCreating] = useState(false)

  // 启动
  const [starting, setStarting] = useState(false)

  useEffect(() => {
    listCollaborationModes().then(r => setModes(r.modes)).catch(() => {})
    listAgents().then(r => setAgents(r.items || [])).catch(() => {})
  }, [])

  const loadList = async () => {
    setLoading(true)
    try {
      const data = await listCollaborations(1, 20)
      setItems(data.items)
      setTotal(data.total)
    } catch {
      toast.error('加载协作列表失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadList() }, [])

  const handleViewDetail = async (collab: Collaboration) => {
    setSelected(collab)
    setDetailOpen(true)
    try {
      const data = await getCollaborationTasks(collab.id)
      setTasks(data.tasks)
    } catch {
      toast.error('加载任务失败')
      setTasks([])
    }
  }

  const handleCreate = async () => {
    if (!formName.trim()) { toast.error('请输入协作名称'); return }
    setCreating(true)
    try {
      const validTasks = formTasks.filter(t => t.agent_id)
      const resp = await createCollaboration({
        name: formName,
        description: formDesc || undefined,
        mode: formMode,
        context: formContext ? { input: formContext } : undefined,
        tasks: validTasks.map((t, i) => ({
          agent_id: t.agent_id,
          role: t.role || undefined,
          input_text: t.input || undefined,
          order: i,
        })),
      })
      toast.success(`协作 "${resp.name}" 已创建`)
      setCreateOpen(false)
      resetForm()
      loadList()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || '创建失败')
    } finally {
      setCreating(false)
    }
  }

  const handleStart = async (id: string) => {
    setStarting(true)
    try {
      const resp = await startCollaboration(id)
      toast.success(resp.message || '协作已启动')
      if (detailOpen) {
        const data = await getCollaborationTasks(id)
        setTasks(data.tasks)
      }
      loadList()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || '启动失败')
    } finally {
      setStarting(false)
    }
  }

  const resetForm = () => {
    setFormName('')
    setFormDesc('')
    setFormMode('sequential')
    setFormContext('')
    setFormTasks([{ agent_id: '', role: 'executor', input: '' }])
  }

  const addFormTask = () => {
    setFormTasks(prev => [...prev, { agent_id: '', role: 'executor', input: '' }])
  }

  const removeFormTask = (idx: number) => {
    if (formTasks.length <= 1) return
    setFormTasks(prev => prev.filter((_, i) => i !== idx))
  }

  const updateFormTask = (idx: number, field: string, value: string) => {
    setFormTasks(prev => prev.map((t, i) => i === idx ? { ...t, [field]: value } : t))
  }

  const statusColors: Record<string, string> = {
    draft: 'bg-gray-100 text-gray-600',
    running: 'bg-blue-100 text-blue-600',
    completed: 'bg-green-100 text-green-600',
    failed: 'bg-red-100 text-red-600',
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">🤝 多智能体协作管理</h1>
          <p className="text-gray-500 mt-1">创建和管理多 Agent 协作任务</p>
        </div>
        <button onClick={() => setCreateOpen(true)} className="px-5 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm">创建协作</button>
      </div>

      {/* 模式卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
        {modes.map(mode => (
          <div key={mode.id} className="bg-white border border-gray-200 rounded-xl p-4 text-center hover:shadow-sm">
            <div className="text-2xl mb-1">{mode.icon}</div>
            <div className="text-sm font-medium">{mode.name}</div>
            <div className="text-xs text-gray-400 mt-0.5 line-clamp-2">{mode.description}</div>
          </div>
        ))}
      </div>

      {/* 列表 */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-5 py-3 border-b bg-gray-50 flex items-center justify-between">
          <h3 className="font-semibold text-sm">协作列表</h3>
          <span className="text-xs text-gray-400">共 {total} 项</span>
        </div>
        {loading ? (
          <div className="flex justify-center py-12"><div className="animate-spin w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full" /></div>
        ) : items.length === 0 ? (
          <div className="text-center py-16 text-gray-400">
            <div className="text-5xl mb-4">🤝</div>
            <p>暂无协作任务</p>
            <button onClick={() => setCreateOpen(true)} className="mt-3 text-blue-600 text-sm hover:underline">创建第一个协作</button>
          </div>
        ) : (
          <div className="divide-y">
            {items.map(c => (
              <div key={c.id} className="px-5 py-4 hover:bg-gray-50 cursor-pointer" onClick={() => handleViewDetail(c)}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusColors[c.status] || 'bg-gray-100'}`}>
                      {c.status === 'draft' ? '草稿' : c.status === 'running' ? '运行中' : c.status === 'completed' ? '已完成' : c.status || '未知'}
                    </span>
                    <div>
                      <span className="font-medium text-sm">{c.name}</span>
                      <span className="ml-2 text-xs text-gray-400">({c.mode})</span>
                      {c.description && <p className="text-xs text-gray-400 mt-0.5">{c.description}</p>}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-400">{c.created_at ? new Date(c.created_at).toLocaleString() : ''}</span>
                    {c.status === 'draft' && (
                      <button onClick={e => { e.stopPropagation(); handleStart(c.id) }} disabled={starting}
                        className="px-3 py-1 bg-green-600 text-white rounded text-xs hover:bg-green-700 disabled:opacity-50">
                        启动
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 创建弹窗 */}
      {createOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setCreateOpen(false)}>
          <div className="bg-white rounded-2xl w-full max-w-2xl max-h-[85vh] overflow-y-auto m-4" onClick={e => e.stopPropagation()}>
            <div className="p-6 border-b"><h2 className="text-xl font-bold">创建协作</h2></div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">名称 *</label>
                <input type="text" value={formName} onChange={e => setFormName(e.target.value)} placeholder="协作名称" className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">描述</label>
                <textarea value={formDesc} onChange={e => setFormDesc(e.target.value)} placeholder="协作描述" rows={2} className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">协作模式</label>
                <div className="grid grid-cols-5 gap-2">
                  {modes.map(m => (
                    <button key={m.id} onClick={() => setFormMode(m.id)}
                      className={`px-3 py-2 rounded-lg text-sm border ${formMode === m.id ? 'border-blue-500 bg-blue-50 text-blue-700' : 'border-gray-200 hover:bg-gray-50'}`}>
                      <div className="text-lg">{m.icon}</div>
                      <div className="text-xs">{m.name}</div>
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">初始上下文（可选）</label>
                <textarea value={formContext} onChange={e => setFormContext(e.target.value)} placeholder="输入初始上下文信息..." rows={2} className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm font-medium">参与 Agent</label>
                  <button onClick={addFormTask} className="text-xs text-blue-600 hover:underline">+ 添加 Agent</button>
                </div>
                {formTasks.map((task, idx) => (
                  <div key={idx} className="flex gap-2 mb-2 items-start">
                    <select value={task.agent_id} onChange={e => updateFormTask(idx, 'agent_id', e.target.value)}
                      className="flex-1 px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                      <option value="">选择 Agent</option>
                      {agents.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
                    </select>
                    <input type="text" value={task.input} onChange={e => updateFormTask(idx, 'input', e.target.value)}
                      placeholder="输入" className="flex-1 px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                    {formTasks.length > 1 && (
                      <button onClick={() => removeFormTask(idx)} className="px-2 py-2 text-red-400 hover:text-red-600 text-sm">✕</button>
                    )}
                  </div>
                ))}
              </div>
            </div>
            <div className="p-6 border-t flex gap-3 justify-end">
              <button onClick={() => setCreateOpen(false)} className="px-5 py-2 border rounded-lg hover:bg-gray-50 text-sm">取消</button>
              <button onClick={handleCreate} disabled={creating} className="px-5 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm">
                {creating ? '创建中...' : '创建协作'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 详情弹窗 */}
      {detailOpen && selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setDetailOpen(false)}>
          <div className="bg-white rounded-2xl w-full max-w-2xl max-h-[85vh] overflow-y-auto m-4" onClick={e => e.stopPropagation()}>
            <div className="p-6 border-b">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-bold">{selected.name}</h2>
                  <div className="flex items-center gap-3 mt-1 text-sm text-gray-500">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusColors[selected.status] || 'bg-gray-100'}`}>
                      {selected.status === 'draft' ? '草稿' : selected.status === 'running' ? '运行中' : selected.status === 'completed' ? '已完成' : selected.status || '未知'}
                    </span>
                    <span>模式: {selected.mode}</span>
                    <span>{selected.created_at ? new Date(selected.created_at).toLocaleString() : ''}</span>
                  </div>
                </div>
                {selected.status === 'draft' && (
                  <button onClick={() => handleStart(selected.id)} disabled={starting}
                    className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 text-sm">
                    {starting ? '启动中...' : '启动协作'}
                  </button>
                )}
              </div>
              {selected.description && <p className="text-sm text-gray-600 mt-2">{selected.description}</p>}
            </div>

            {/* 任务列表 */}
            <div className="p-6">
              <h3 className="font-semibold mb-3">任务流程</h3>
              {tasks.length === 0 ? (
                <p className="text-sm text-gray-400">暂无任务</p>
              ) : (
                <div className="space-y-3">
                  {tasks.map((task, idx) => (
                    <div key={task.id} className="border border-gray-200 rounded-xl p-4">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className="w-6 h-6 rounded-full bg-blue-100 text-blue-600 text-xs flex items-center justify-center font-medium">{idx + 1}</span>
                          <span className="font-medium text-sm">{task.agent_name || task.agent_id}</span>
                          {task.role && <span className="px-2 py-0.5 bg-gray-100 text-xs rounded-full">{task.role}</span>}
                        </div>
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusColors[task.status] || 'bg-gray-100'}`}>
                          {task.status === 'pending' ? '等待' : task.status === 'running' ? '执行中' : task.status === 'completed' ? '完成' : task.status === 'failed' ? '失败' : task.status}
                        </span>
                      </div>
                      {task.input_text && (
                        <div className="bg-gray-50 p-2 rounded text-xs text-gray-600 mb-1">
                          <span className="text-gray-400">输入: </span>{task.input_text}
                        </div>
                      )}
                      {task.output_text && (
                        <div className="bg-green-50 p-2 rounded text-xs text-green-700">
                          <span className="text-green-500">输出: </span>{task.output_text}
                        </div>
                      )}
                      {task.error_message && <p className="text-xs text-red-500 mt-1">{task.error_message}</p>}
                    </div>
                  ))}
                </div>
              )}

              {/* 结果 */}
              {selected.result && (
                <div className="mt-6 border-t pt-4">
                  <h3 className="font-semibold mb-2">协作结果</h3>
                  <pre className="bg-gray-50 p-4 rounded-lg text-xs overflow-x-auto">{JSON.stringify(selected.result, null, 2)}</pre>
                </div>
              )}
            </div>

            <div className="p-6 border-t flex justify-end">
              <button onClick={() => setDetailOpen(false)} className="px-5 py-2 border rounded-lg hover:bg-gray-50 text-sm">关闭</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default CollaborationsPage
