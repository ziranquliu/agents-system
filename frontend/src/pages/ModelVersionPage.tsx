/**
 * 模型版本管理页面
 */
import React, { useState, useEffect } from 'react'
import { 
  Clock, 
  RotateCcw, 
  Server, 
  RefreshCw, 
  Trash2,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  CheckCircle
} from 'lucide-react'
import { useModelTemplateStore } from '../stores/modelConfigStore'
import { formatDistanceToNow } from 'date-fns'
import { zhCN } from 'date-fns/locale'

interface VersionItem {
  id: string
  template_id: string
  version: number
  name: string
  provider: string
  model: string
  config: string
  change_log: string
  created_by: string
  created_at: string
}

interface BindingItem {
  id: string
  template_id: string
  agent_id: string
  sync_mode: string
  override_config: string
  gray_percentage: int
  gray_status: string
  last_synced_at: string
  agent_name?: string
  agent_status?: string
}

const VersionTimeline: React.FC<{ versions: VersionItem[] }> = ({ versions }) => {
  return (
    <div className="relative">
      {/* 时间线主线 */}
      <div className="absolute left-4 top-0 bottom-0 w-px bg-gray-200" />
      
      {/* 版本节点 */}
      {versions.map((version, index) => (
        <div key={version.id} className="relative flex gap-4 mb-6">
          {/* 节点圆点 */}
          <div className="absolute left-2 top-1 w-4 h-4 rounded-full bg-blue-500 border-4 border-white shadow" />
          
          {/* 内容卡片 */}
          <div className="flex-1 ml-8 bg-white rounded-lg border border-gray-200 p-4 hover:shadow-md transition-shadow">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-sm font-medium">
                    v{version.version}
                  </span>
                  {index === 0 && (
                    <span className="px-2 py-1 bg-green-100 text-green-700 rounded text-xs">
                      当前版本
                    </span>
                  )}
                </div>
                <p className="mt-2 text-gray-800 font-medium">{version.name}</p>
                <p className="text-sm text-gray-500 mt-1">
                  {version.provider} / {version.model}
                </p>
              </div>
              
              <div className="text-right text-sm text-gray-400">
                <p>{formatDistanceToNow(new Date(version.created_at), { locale: zhCN })}前</p>
                <p>由 {version.created_by?.slice(0, 8)}... 创建</p>
              </div>
            </div>
            
            {version.change_log && (
              <div className="mt-3 p-3 bg-gray-50 rounded text-sm text-gray-600">
                <span className="font-medium">变更说明：</span>
                {version.change_log}
              </div>
            )}
            
            <details className="mt-3">
              <summary className="cursor-pointer text-sm text-blue-600 hover:text-blue-700">
                查看配置详情
              </summary>
              <pre className="mt-2 p-3 bg-gray-900 text-gray-100 rounded text-xs overflow-x-auto">
                {JSON.stringify(JSON.parse(version.config || '{}'), null, 2)}
              </pre>
            </details>
            
            <div className="mt-3 flex gap-2">
              <button 
                className="flex items-center gap-1 px-3 py-1.5 text-sm bg-gray-100 hover:bg-gray-200 rounded transition-colors"
                onClick={() => handleRollback(version.version)}
              >
                <RotateCcw size={14} />
                回滚到此版本
              </button>
              <button 
                className="flex items-center gap-1 px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 rounded transition-colors"
                onClick={() => handleDelete(version.version)}
              >
                <Trash2 size={14} />
                删除
              </button>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

const AgentBindingList: React.FC<{ bindings: BindingItem[] }> = ({ bindings }) => {
  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Agent</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">同步模式</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">状态</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">最后同步</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">操作</th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {bindings.map((binding) => (
            <tr key={binding.id} className="hover:bg-gray-50">
              <td className="px-6 py-4">
                <div className="flex items-center">
                  <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center mr-3">
                    <Server size={16} className="text-blue-600" />
                  </div>
                  <div>
                    <p className="font-medium text-gray-900">{binding.agent_name || binding.agent_id}</p>
                    <p className="text-sm text-gray-500">{binding.agent_id}</p>
                  </div>
                </div>
              </td>
              <td className="px-6 py-4">
                <span className={`px-2 py-1 rounded text-xs ${
                  binding.sync_mode === 'auto' ? 'bg-green-100 text-green-700' :
                  binding.sync_mode === 'manual' ? 'bg-yellow-100 text-yellow-700' :
                  'bg-purple-100 text-purple-700'
                }`}>
                  {binding.sync_mode}
                </span>
              </td>
              <td className="px-6 py-4">
                <span className={`flex items-center gap-1 text-sm ${
                  binding.gray_status === 'synced' ? 'text-green-600' :
                  binding.gray_status === 'outdated' ? 'text-yellow-600' :
                  'text-red-600'
                }`}>
                  {binding.gray_status === 'synced' ? <CheckCircle size={14} /> : 
                   binding.gray_status === 'outdated' ? <AlertCircle size={14} /> :
                   <AlertCircle size={14} />}
                  {binding.gray_status}
                </span>
              </td>
              <td className="px-6 py-4 text-sm text-gray-500">
                {binding.last_synced_at 
                  ? formatDistanceToNow(new Date(binding.last_synced_at), { locale: zhCN }) + '前'
                  : '从未同步'}
              </td>
              <td className="px-6 py-4">
                <button 
                  className="text-blue-600 hover:text-blue-700 text-sm"
                  onClick={() => handleSync(binding.template_id, binding.agent_id)}
                >
                  强制同步
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const ModelVersionPage: React.FC<{ templateId: string }> = ({ templateId }) => {
  const { templates, fetchVersions, fetchBindings, rollbackVersion, deleteVersion, syncTemplate } = useModelTemplateStore()
  
  const [versions, setVersions] = useState<VersionItem[]>([])
  const [bindings, setBindings] = useState<BindingItem[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'versions' | 'bindings'>('versions')
  
  useEffect(() => {
    loadVersions()
    loadBindings()
  }, [templateId])
  
  const loadVersions = async () => {
    setLoading(true)
    try {
      const data = await fetchVersions(templateId)
      setVersions(data.items || [])
    } catch (error) {
      console.error('Failed to load versions:', error)
    } finally {
      setLoading(false)
    }
  }
  
  const loadBindings = async () => {
    try {
      const data = await fetchBindings(templateId)
      setBindings(data.items || [])
    } catch (error) {
      console.error('Failed to load bindings:', error)
    }
  }
  
  const handleRollback = async (version: number) => {
    if (!confirm(`确定要回滚到版本 ${version} 吗？`)) return
    
    try {
      await rollbackVersion(templateId, version)
      await loadVersions()
      alert('回滚成功')
    } catch (error) {
      alert('回滚失败: ' + (error as Error).message)
    }
  }
  
  const handleDelete = async (version: number) => {
    if (!confirm(`确定要删除版本 ${version} 吗？此操作不可恢复。`)) return
    
    try {
      await deleteVersion(templateId, version)
      await loadVersions()
      alert('删除成功')
    } catch (error) {
      alert('删除失败: ' + (error as Error).message)
    }
  }
  
  const handleSync = async (templateId: string, agentId: string) => {
    try {
      await syncTemplate(templateId, { force: true })
      await loadBindings()
      alert('同步成功')
    } catch (error) {
      alert('同步失败: ' + (error as Error).message)
    }
  }
  
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="animate-spin text-blue-500" size={32} />
      </div>
    )
  }
  
  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">模型版本管理</h1>
        <button 
          className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
          onClick={() => handleSync(templateId, '')}
        >
          <RefreshCw size={16} />
          同步所有绑定
        </button>
      </div>
      
      {/* 标签页切换 */}
      <div className="flex border-b border-gray-200">
        <button
          className={`px-6 py-3 font-medium text-sm ${
            activeTab === 'versions' 
              ? 'border-b-2 border-blue-500 text-blue-600' 
              : 'text-gray-500 hover:text-gray-700'
          }`}
          onClick={() => setActiveTab('versions')}
        >
          版本历史 ({versions.length})
        </button>
        <button
          className={`px-6 py-3 font-medium text-sm ${
            activeTab === 'bindings' 
              ? 'border-b-2 border-blue-500 text-blue-600' 
              : 'text-gray-500 hover:text-gray-700'
          }`}
          onClick={() => setActiveTab('bindings')}
        >
          绑定Agent ({bindings.length})
        </button>
      </div>
      
      {/* 版本历史 */}
      {activeTab === 'versions' && (
        <div>
          {versions.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <Clock size={48} className="mx-auto mb-4 opacity-30" />
              <p>暂无版本历史</p>
            </div>
          ) : (
            <VersionTimeline versions={versions} />
          )}
        </div>
      )}
      
      {/* 绑定Agent列表 */}
      {activeTab === 'bindings' && (
        <AgentBindingList bindings={bindings} />
      )}
    </div>
  )
}

export default ModelVersionPage
