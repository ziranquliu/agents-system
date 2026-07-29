import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAgentStore } from '../stores/agentStore'
import { useModelConfigStore } from '../stores/modelConfigStore'
import { useSkillStore } from '../stores/skillStore'
import { useMCPServerStore } from '../stores/mcpServerStore'
import { Loading, Empty } from '../components/ui'
import * as convApi from '../api/conversations'

const statusConfig: Record<string, { label: string; color: string }> = {
  draft: { label: '草稿', color: 'bg-gray-100 text-gray-600' },
  running: { label: '运行中', color: 'bg-green-100 text-green-700' },
  stopped: { label: '已停止', color: 'bg-yellow-100 text-yellow-700' },
  error: { label: '异常', color: 'bg-red-100 text-red-700' },
  archived: { label: '已归档', color: 'bg-slate-100 text-slate-600' },
}

export default function Dashboard() {
  const { agents, fetchAgents } = useAgentStore()
  const { items: models, fetch: fetchModels } = useModelConfigStore()
  const { items: skills, fetch: fetchSkills } = useSkillStore()
  const { items: mcps, fetch: fetchMcps } = useMCPServerStore()
  const [convCount, setConvCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState({
    total: 0, draft: 0, running: 0, stopped: 0, error: 0, archived: 0,
  })

  useEffect(() => {
    Promise.all([
      fetchAgents({ pageSize: 100 }),
      fetchModels({ pageSize: 1 }),
      fetchSkills({ pageSize: 1 }),
      fetchMcps({ pageSize: 1 }),
      convApi.listConversations({ page_size: 1 }).then(r => setConvCount(r.total)),
    ]).catch(() => {}).finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    setStats({
      total: agents.length,
      draft: agents.filter((a) => a.status === 'draft').length,
      running: agents.filter((a) => a.status === 'running').length,
      stopped: agents.filter((a) => a.status === 'stopped').length,
      error: agents.filter((a) => a.status === 'error').length,
      archived: agents.filter((a) => a.status === 'archived').length,
    })
  }, [agents])

  const statCards = [
    { label: 'Agent 总数', value: stats.total, icon: '🤖', bg: 'bg-blue-50', text: 'text-blue-700' },
    { label: '运行中', value: stats.running, icon: '▶️', bg: 'bg-green-50', text: 'text-green-700' },
    { label: '模型配置', value: models.length, icon: '🧠', bg: 'bg-purple-50', text: 'text-purple-700' },
    { label: '对话', value: convCount, icon: '💬', bg: 'bg-cyan-50', text: 'text-cyan-700' },
    { label: 'Skills', value: skills.length, icon: '🔧', bg: 'bg-amber-50', text: 'text-amber-700' },
    { label: 'MCP 服务', value: mcps.length, icon: '🔗', bg: 'bg-indigo-50', text: 'text-indigo-700' },
  ]

  const quickActions = [
    { label: '创建 Agent', path: '/agents', icon: '➕', desc: '创建新的智能体' },
    { label: '查看对话', path: '/conversations', icon: '💬', desc: '浏览对话历史' },
    { label: '模型配置', path: '/models', icon: '🧠', desc: '管理模型参数' },
    { label: 'Skill 管理', path: '/skills', icon: '🔧', desc: '配置智能体技能' },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">总览看板</h1>
        <p className="text-gray-500 mt-1">系统运行概览</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {statCards.map((card) => (
          <div key={card.label} className={`${card.bg} rounded-xl p-4 border border-transparent hover:shadow-sm transition-shadow`}>
            <div className="text-2xl mb-2">{card.icon}</div>
            <div className={`text-2xl font-bold ${card.text}`}>{card.value}</div>
            <div className="text-sm text-gray-500 mt-1">{card.label}</div>
          </div>
        ))}
      </div>

      <div>
        <h2 className="text-lg font-semibold text-gray-800 mb-3">快速操作</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {quickActions.map((action) => (
            <Link key={action.path} to={action.path} className="bg-white rounded-xl p-4 border border-gray-200 hover:border-blue-300 hover:shadow-sm transition-all">
              <div className="text-2xl mb-2">{action.icon}</div>
              <div className="font-medium text-gray-800">{action.label}</div>
              <div className="text-sm text-gray-500 mt-1">{action.desc}</div>
            </Link>
          ))}
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-gray-800">最近 Agent</h2>
          <Link to="/agents" className="text-sm text-blue-600 hover:text-blue-700">查看全部 →</Link>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          {loading ? (
            <Loading fullPage text="加载 Agent 列表..." />
          ) : agents.length === 0 ? (
            <Empty icon="🤖" title="暂无 Agent" description="还没有创建任何 Agent" />
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">名称</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">状态</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">模型</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">创建时间</th>
                </tr>
              </thead>
              <tbody>
                {agents.slice(0, 5).map((agent) => (
                  <tr key={agent.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3">
                      <Link to={`/agents/${agent.id}`} className="text-sm font-medium text-blue-600 hover:text-blue-700">{agent.name}</Link>
                    </td>
                    <td className="px-4 py-3"><span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium ${statusConfig[agent.status]?.color || 'bg-gray-100 text-gray-600'}`}>{statusConfig[agent.status]?.label || agent.status}</span></td>
                    <td className="px-4 py-3 text-sm text-gray-600">{agent.model_name || '-'}</td>
                    <td className="px-4 py-3 text-sm text-gray-500">{new Date(agent.created_at).toLocaleDateString('zh-CN')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
