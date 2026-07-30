import React, { useEffect, useState } from 'react'
import { getAvailableUpdates, refreshUpdates, applyUpdate, UpdateItem } from '../api/updates'
import { useToast } from '../components/ui'

const UpdateCenter: React.FC = () => {
  const toast = useToast()
  const [updates, setUpdates] = useState<UpdateItem[]>([])
  const [loading, setLoading] = useState(false)
  const [checking, setChecking] = useState(false)
  const [applying, setApplying] = useState<string | null>(null)

  const loadUpdates = async () => {
    setLoading(true)
    try {
      const data = await getAvailableUpdates()
      setUpdates(data.updates)
    } catch {
      toast.error('加载更新信息失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadUpdates() }, [])

  const handleRefresh = async () => {
    setChecking(true)
    try {
      const resp = await refreshUpdates()
      toast.success(`检查完成，发现 ${resp.updates_count} 个更新`)
      loadUpdates()
    } catch {
      toast.error('检查更新失败')
    } finally {
      setChecking(false)
    }
  }

  const handleApply = async (item: UpdateItem) => {
    setApplying(item.component_id)
    try {
      const resp = await applyUpdate(item.component_type, item.component_id)
      toast.success(resp.message || '更新成功')
      loadUpdates()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || '更新失败')
    } finally {
      setApplying(null)
    }
  }

  const typeLabels: Record<string, string> = {
    skill: 'Skill', mcp: 'MCP', agent: 'Agent', model: '模型',
  }

  const typeColors: Record<string, string> = {
    skill: 'text-purple-600 bg-purple-50',
    mcp: 'text-teal-600 bg-teal-50',
    agent: 'text-blue-600 bg-blue-50',
    model: 'text-orange-600 bg-orange-50',
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">🔄 统一更新检测中心</h1>
          <p className="text-gray-500 mt-1">检测并更新系统中各组件的版本</p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={checking}
          className="px-5 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm flex items-center gap-2"
        >
          {checking && <div className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" />}
          {checking ? '检查中...' : '检查更新'}
        </button>
      </div>

      {/* 状态卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <div className="text-3xl font-bold text-gray-800">{updates.length}</div>
          <div className="text-sm text-gray-500 mt-1">待更新组件</div>
        </div>
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <div className="text-3xl font-bold text-purple-600">{updates.filter(u => u.component_type === 'skill').length}</div>
          <div className="text-sm text-gray-500 mt-1">Skill 更新</div>
        </div>
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <div className="text-3xl font-bold text-teal-600">{updates.filter(u => u.component_type === 'mcp').length}</div>
          <div className="text-sm text-gray-500 mt-1">MCP 更新</div>
        </div>
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <div className="text-3xl font-bold text-blue-600">{updates.filter(u => u.component_type === 'agent').length + updates.filter(u => u.component_type === 'model').length}</div>
          <div className="text-sm text-gray-500 mt-1">Agent/模型更新</div>
        </div>
      </div>

      {/* 更新列表 */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-5 py-3 border-b bg-gray-50 flex items-center justify-between">
          <h3 className="font-semibold text-sm">可更新的组件</h3>
          <span className="text-xs text-gray-400">{updates.length} 项</span>
        </div>

        {loading ? (
          <div className="flex justify-center py-12">
            <div className="animate-spin w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full" />
          </div>
        ) : updates.length === 0 ? (
          <div className="text-center py-16 text-gray-400">
            <div className="text-5xl mb-4">✅</div>
            <p>所有组件已是最新版本</p>
            <p className="text-xs mt-2">点击"检查更新"按钮重新检测</p>
          </div>
        ) : (
          <div className="divide-y">
            {updates.map(item => (
              <div key={`${item.component_type}-${item.component_id}`} className="px-5 py-4 hover:bg-gray-50">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="text-2xl">{item.icon || '📦'}</span>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${typeColors[item.component_type] || 'text-gray-600 bg-gray-50'}`}>
                          {typeLabels[item.component_type] || item.component_type}
                        </span>
                        <span className="font-medium text-sm">{item.component_name}</span>
                      </div>
                      <div className="flex items-center gap-3 mt-1 text-xs">
                        <span className="text-gray-400">
                          当前: <span className="text-gray-600">{item.current_version}</span>
                        </span>
                        <span className="text-gray-300">→</span>
                        <span className="text-green-600 font-medium">{item.latest_version}</span>
                      </div>
                      {item.description && (
                        <p className="text-xs text-gray-400 mt-0.5 line-clamp-1">{item.description}</p>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={() => handleApply(item)}
                    disabled={applying === item.component_id}
                    className="px-4 py-1.5 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 text-xs flex items-center gap-1 flex-shrink-0"
                  >
                    {applying === item.component_id ? (
                      <><div className="animate-spin w-3 h-3 border-2 border-white border-t-transparent rounded-full" /> 更新中</>
                    ) : '更新'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default UpdateCenter
