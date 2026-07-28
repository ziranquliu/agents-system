import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useAgentStore } from '../stores/agentStore'
import type { AgentUpdatePayload } from '../api/agents'

const statusConfig: Record<string, { label: string; color: string }> = {
  draft: { label: '草稿', color: 'bg-gray-100 text-gray-600' },
  running: { label: '运行中', color: 'bg-green-100 text-green-700' },
  stopped: { label: '已停止', color: 'bg-yellow-100 text-yellow-700' },
  error: { label: '异常', color: 'bg-red-100 text-red-700' },
  archived: { label: '已归档', color: 'bg-slate-100 text-slate-600' },
}

const statusTransitions: Record<string, string[]> = {
  draft: ['running', 'archived'],
  running: ['stopped', 'error'],
  stopped: ['running', 'archived'],
  error: ['stopped', 'draft'],
  archived: [],
}

export default function AgentDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const {
    selectedAgent: agent, loading, error,
    fetchAgent, updateAgent, updateStatus, deleteAgent,
  } = useAgentStore()

  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState<AgentUpdatePayload>({})
  const [saveError, setSaveError] = useState('')
  const [statusLoading, setStatusLoading] = useState(false)

  useEffect(() => {
    if (id) fetchAgent(id)
  }, [id])

  useEffect(() => {
    if (agent && !editing) {
      setForm({
        name: agent.name,
        description: agent.description,
        system_prompt: agent.system_prompt,
        welcome_message: agent.welcome_message,
        model_provider: agent.model_provider,
        model_name: agent.model_name,
        temperature: agent.temperature,
        max_tokens: agent.max_tokens,
        context_window: agent.context_window,
      })
    }
  }, [agent, editing])

  const handleSave = async () => {
    if (!id) return
    setSaveError('')
    try {
      await updateAgent(id, form)
      setEditing(false)
    } catch (err: any) {
      setSaveError(err?.response?.data?.detail || '保存失败')
    }
  }

  const handleStatusChange = async (newStatus: string) => {
    if (!id) return
    setStatusLoading(true)
    try {
      await updateStatus(id, newStatus)
    } catch {
      alert('状态变更失败')
    } finally {
      setStatusLoading(false)
    }
  }

  const handleDelete = async () => {
    if (!id || !window.confirm(`确定要删除 Agent「${agent?.name}」吗？`)) return
    await deleteAgent(id)
    navigate('/agents')
  }

  if (loading && !agent) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-400">加载中...</div>
      </div>
    )
  }

  if (error && !agent) {
    return (
      <div className="space-y-4">
        <div className="bg-red-50 text-red-600 text-sm px-4 py-3 rounded-lg border border-red-100">
          {error}
        </div>
        <button
          onClick={() => navigate('/agents')}
          className="text-blue-600 hover:text-blue-700 text-sm"
        >
          ← 返回列表
        </button>
      </div>
    )
  }

  if (!agent) return null

  const currentStatus = statusConfig[agent.status] || { label: agent.status, color: 'bg-gray-100 text-gray-600' }
  const allowedTransitions = statusTransitions[agent.status] || []

  return (
    <div className="space-y-6">
      {/* 返回导航 */}
      <div className="flex items-center gap-3 text-sm">
        <button
          onClick={() => navigate('/agents')}
          className="text-gray-500 hover:text-gray-700 transition-colors"
        >
          ← Agent 列表
        </button>
        <span className="text-gray-300">/</span>
        <span className="text-gray-900 font-medium">{agent.name}</span>
      </div>

      {/* 错误提示 */}
      {saveError && (
        <div className="bg-red-50 text-red-600 text-sm px-4 py-3 rounded-lg border border-red-100">
          {saveError}
        </div>
      )}

      {/* 基本信息卡片 */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold text-gray-900">基本信息</h2>
            <span
              className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium ${currentStatus.color}`}
            >
              {currentStatus.label}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {!editing ? (
              <>
                <button
                  onClick={() => setEditing(true)}
                  className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  编辑
                </button>
                <button
                  onClick={handleDelete}
                  className="px-3 py-1.5 text-sm text-red-600 border border-red-200 rounded-lg hover:bg-red-50 transition-colors"
                >
                  删除
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={() => {
                    setEditing(false)
                    setForm({
                      name: agent.name,
                      description: agent.description,
                      system_prompt: agent.system_prompt,
                      welcome_message: agent.welcome_message,
                      model_provider: agent.model_provider,
                      model_name: agent.model_name,
                      temperature: agent.temperature,
                      max_tokens: agent.max_tokens,
                      context_window: agent.context_window,
                    })
                  }}
                  className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  取消
                </button>
                <button
                  onClick={handleSave}
                  className="px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
                >
                  保存
                </button>
              </>
            )}
          </div>
        </div>

        <div className="p-6 space-y-5">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {/* 名称 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">名称</label>
              {editing ? (
                <input
                  type="text"
                  value={form.name || ''}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none text-sm"
                />
              ) : (
                <p className="text-sm text-gray-900 py-2">{agent.name}</p>
              )}
            </div>

            {/* 模型名称 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">模型</label>
              {editing ? (
                <input
                  type="text"
                  value={form.model_name || ''}
                  onChange={(e) => setForm({ ...form, model_name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none text-sm"
                  placeholder="如 gpt-4o"
                />
              ) : (
                <p className="text-sm text-gray-900 py-2">{agent.model_name || '-'}</p>
              )}
            </div>

            {/* 模型提供商 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">模型提供商</label>
              {editing ? (
                <select
                  value={form.model_provider || ''}
                  onChange={(e) => setForm({ ...form, model_provider: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                >
                  <option value="">请选择</option>
                  <option value="openai">OpenAI</option>
                  <option value="ollama">Ollama</option>
                  <option value="openrouter">OpenRouter</option>
                  <option value="anthropic">Anthropic</option>
                  <option value="other">其他</option>
                </select>
              ) : (
                <p className="text-sm text-gray-900 py-2">{agent.model_provider || '-'}</p>
              )}
            </div>

            {/* 温度 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                温度 (Temperature): {form.temperature ?? agent.temperature ?? 0.7}
              </label>
              {editing ? (
                <input
                  type="range"
                  min="0"
                  max="2"
                  step="0.1"
                  value={form.temperature ?? agent.temperature ?? 0.7}
                  onChange={(e) => setForm({ ...form, temperature: parseFloat(e.target.value) })}
                  className="w-full"
                />
              ) : (
                <p className="text-sm text-gray-900 py-2">{agent.temperature ?? 0.7}</p>
              )}
            </div>

            {/* 最大 Token */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">最大 Token</label>
              {editing ? (
                <input
                  type="number"
                  value={form.max_tokens ?? agent.max_tokens ?? 4096}
                  onChange={(e) => setForm({ ...form, max_tokens: parseInt(e.target.value) || 4096 })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none text-sm"
                />
              ) : (
                <p className="text-sm text-gray-900 py-2">{agent.max_tokens ?? 4096}</p>
              )}
            </div>

            {/* 上下文窗口 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">上下文窗口</label>
              {editing ? (
                <input
                  type="number"
                  value={form.context_window ?? agent.context_window ?? 8192}
                  onChange={(e) => setForm({ ...form, context_window: parseInt(e.target.value) || 8192 })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none text-sm"
                />
              ) : (
                <p className="text-sm text-gray-900 py-2">{agent.context_window ?? 8192}</p>
              )}
            </div>
          </div>

          {/* 描述 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
            {editing ? (
              <textarea
                value={form.description || ''}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none text-sm resize-none"
                rows={3}
              />
            ) : (
              <p className="text-sm text-gray-900 py-2">{agent.description || '暂无描述'}</p>
            )}
          </div>

          {/* 系统提示词 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">系统提示词</label>
            {editing ? (
              <textarea
                value={form.system_prompt || ''}
                onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none text-sm resize-none font-mono"
                rows={5}
                placeholder="设置 Agent 的系统提示词..."
              />
            ) : (
              <div className="text-sm text-gray-900 py-2 bg-gray-50 rounded-lg px-3 whitespace-pre-wrap">
                {agent.system_prompt || '未设置'}
              </div>
            )}
          </div>

          {/* 欢迎消息 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">欢迎消息</label>
            {editing ? (
              <textarea
                value={form.welcome_message || ''}
                onChange={(e) => setForm({ ...form, welcome_message: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none text-sm resize-none"
                rows={3}
                placeholder="设置新对话时的欢迎消息..."
              />
            ) : (
              <p className="text-sm text-gray-900 py-2">{agent.welcome_message || '未设置'}</p>
            )}
          </div>
        </div>
      </div>

      {/* 状态管理卡片 */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-semibold text-gray-900">状态管理</h2>
        </div>
        <div className="p-6">
          <div className="flex items-center gap-3 mb-4">
            <span className="text-sm text-gray-500">当前状态：</span>
            <span
              className={`inline-block px-3 py-1 rounded-full text-sm font-medium ${currentStatus.color}`}
            >
              {currentStatus.label}
            </span>
          </div>
          {allowedTransitions.length > 0 ? (
            <div className="flex flex-wrap gap-3">
              {allowedTransitions.map((target) => (
                <button
                  key={target}
                  onClick={() => handleStatusChange(target)}
                  disabled={statusLoading}
                  className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors disabled:opacity-50 ${
                    target === 'running'
                      ? 'bg-green-100 text-green-700 hover:bg-green-200'
                      : target === 'stopped'
                      ? 'bg-yellow-100 text-yellow-700 hover:bg-yellow-200'
                      : target === 'archived'
                      ? 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                      : target === 'draft'
                      ? 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  {statusConfig[target]?.label || target}
                </button>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-400">已归档的 Agent 无法变更状态</p>
          )}
        </div>
      </div>

      {/* 元信息卡片 */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-semibold text-gray-900">元信息</h2>
        </div>
        <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs text-gray-500 mb-1">ID</label>
            <p className="text-sm text-gray-900 font-mono">{agent.id}</p>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">创建时间</label>
            <p className="text-sm text-gray-900">
              {new Date(agent.created_at).toLocaleString('zh-CN')}
            </p>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">更新时间</label>
            <p className="text-sm text-gray-900">
              {agent.updated_at
                ? new Date(agent.updated_at).toLocaleString('zh-CN')
                : '-'}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
