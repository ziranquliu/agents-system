import React, { useEffect, useState } from 'react'
import { getCacheStats, clearCache, getExecutionStats, getDagPlan } from '../api/skillOptimization'
import { useToast } from '../components/ui'

const SkillOptimization: React.FC = () => {
  const toast = useToast()
  const [cache, setCache] = useState<any>(null)
  const [execStats, setExecStats] = useState<any>(null)
  const [dagInput, setDagInput] = useState('')
  const [dagPlan, setDagPlan] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [dagLoading, setDagLoading] = useState(false)

  const loadData = async () => {
    setLoading(true)
    try {
      const [c, s] = await Promise.all([getCacheStats(), getExecutionStats()])
      setCache(c)
      setExecStats(s)
    } catch {
      toast.error('加载优化数据失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadData() }, [])

  const handleClearCache = async () => {
    try {
      const resp = await clearCache()
      setCache(resp.stats)
      toast.success('缓存已清除')
    } catch {
      toast.error('清除缓存失败')
    }
  }

  const handleDagPlan = async () => {
    const ids = dagInput.split(',').map(s => s.trim()).filter(Boolean)
    if (ids.length < 2) { toast.error('请输入至少 2 个 Skill ID'); return }
    setDagLoading(true)
    try {
      const plan = await getDagPlan(ids)
      setDagPlan(plan)
    } catch {
      toast.error('计算 DAG 计划失败')
    } finally {
      setDagLoading(false)
    }
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <h1 className="text-2xl font-bold flex items-center gap-2 mb-6">⚡ Skill 使用优化</h1>

      {loading ? (
        <div className="flex justify-center py-12"><div className="animate-spin w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full" /></div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* 缓存统计 */}
          <div className="bg-white border border-gray-200 rounded-xl p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold">📦 LRU 缓存</h2>
              <button onClick={handleClearCache} className="px-3 py-1.5 bg-red-50 text-red-600 rounded-lg text-xs hover:bg-red-100">清除缓存</button>
            </div>
            {cache && (
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="bg-gray-50 p-3 rounded-lg">
                  <span className="text-gray-400">类型</span>
                  <p className="font-medium">{cache.cache_type}</p>
                </div>
                <div className="bg-gray-50 p-3 rounded-lg">
                  <span className="text-gray-400">容量</span>
                  <p className="font-medium">{cache.capacity}</p>
                </div>
                <div className="bg-gray-50 p-3 rounded-lg">
                  <span className="text-gray-400">当前大小</span>
                  <p className="font-medium">{cache.size}</p>
                </div>
                <div className="bg-gray-50 p-3 rounded-lg">
                  <span className="text-gray-400">命中率</span>
                  <p className="font-medium text-green-600">{cache.hit_rate}%</p>
                </div>
                <div className="bg-gray-50 p-3 rounded-lg">
                  <span className="text-gray-400">命中</span>
                  <p className="font-medium">{cache.hits}</p>
                </div>
                <div className="bg-gray-50 p-3 rounded-lg">
                  <span className="text-gray-400">未命中</span>
                  <p className="font-medium">{cache.misses}</p>
                </div>
              </div>
            )}
          </div>

          {/* 执行统计 */}
          <div className="bg-white border border-gray-200 rounded-xl p-6">
            <h2 className="font-semibold mb-4">📊 执行统计</h2>
            {execStats ? (
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="bg-gray-50 p-3 rounded-lg">
                  <span className="text-gray-400">Skill 数量</span>
                  <p className="font-medium">{execStats.total_skills || 0}</p>
                </div>
                <div className="bg-gray-50 p-3 rounded-lg">
                  <span className="text-gray-400">总执行次数</span>
                  <p className="font-medium">{execStats.total_executions || 0}</p>
                </div>
                <div className="bg-gray-50 p-3 rounded-lg">
                  <span className="text-gray-400">平均耗时</span>
                  <p className="font-medium">{execStats.avg_duration_ms || '-'} ms</p>
                </div>
              </div>
            ) : <p className="text-sm text-gray-400">暂无执行数据</p>}
          </div>

          {/* DAG 执行计划 */}
          <div className="lg:col-span-2 bg-white border border-gray-200 rounded-xl p-6">
            <h2 className="font-semibold mb-4">🔀 DAG 执行计划</h2>
            <div className="flex gap-3 mb-4">
              <input
                type="text"
                value={dagInput}
                onChange={e => setDagInput(e.target.value)}
                placeholder="输入 Skill ID，用逗号分隔（如: code-review,data-vis,translate）"
                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button onClick={handleDagPlan} disabled={dagLoading}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm">
                {dagLoading ? '计算中...' : '计算计划'}
              </button>
            </div>
            {dagPlan && (
              <div>
                <p className="text-xs text-gray-400 mb-3">{dagPlan.suggestion}</p>
                <div className="space-y-2">
                  {dagPlan.levels.map((level: string[], idx: number) => (
                    <div key={idx} className="flex items-center gap-2">
                      <span className="w-8 h-8 rounded-full bg-blue-100 text-blue-600 text-xs flex items-center justify-center font-medium">
                        L{idx + 1}
                      </span>
                      <div className="flex gap-2 flex-wrap">
                        {level.map((sid: string) => (
                          <span key={sid} className="px-3 py-1.5 bg-gray-100 rounded-lg text-sm">{sid}</span>
                        ))}
                      </div>
                      {idx < dagPlan.levels.length - 1 && <span className="text-gray-300 text-sm">↓</span>}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default SkillOptimization
