import React, { useEffect, useState } from 'react'
import { getTokenStats, resetTokenStats, suggestContextWindow } from '../api/conversationEnhancement'
import { useToast } from '../components/ui'

const ConversationEnhancement: React.FC = () => {
  const toast = useToast()
  const [stats, setStats] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [ctxLen, setCtxLen] = useState('50')
  const [ctxSuggest, setCtxSuggest] = useState<any>(null)

  const loadData = async () => {
    setLoading(true)
    try {
      const s = await getTokenStats()
      setStats(s)
    } catch { toast.error('加载数据失败') }
    finally { setLoading(false) }
  }

  useEffect(() => { loadData() }, [])

  const handleReset = async () => {
    try {
      await resetTokenStats()
      toast.success('Token 统计已重置')
      loadData()
    } catch { toast.error('重置失败') }
  }

  const handleSuggest = async () => {
    const len = parseInt(ctxLen) || 10
    try {
      const resp = await suggestContextWindow(len)
      setCtxSuggest(resp)
    } catch { toast.error('建议获取失败') }
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <h1 className="text-2xl font-bold flex items-center gap-2 mb-6">💬 会话管理增强</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Token 统计 */}
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold">Token 使用统计</h2>
            <button onClick={handleReset} className="px-3 py-1.5 bg-red-50 text-red-600 rounded text-xs hover:bg-red-100">重置</button>
          </div>
          {loading ? (
            <div className="animate-spin w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full mx-auto" />
          ) : stats ? (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="bg-gray-50 p-3 rounded-lg"><span className="text-gray-400">总 Token</span><p className="font-medium">{(stats.total_tokens || 0).toLocaleString()}</p></div>
                <div className="bg-gray-50 p-3 rounded-lg"><span className="text-gray-400">总消息</span><p className="font-medium">{(stats.total_messages || 0).toLocaleString()}</p></div>
                <div className="bg-gray-50 p-3 rounded-lg"><span className="text-gray-400">模型数</span><p className="font-medium">{stats.models_count || 0}</p></div>
              </div>
              {/* 按模型统计 */}
              {stats.by_model && Object.keys(stats.by_model).length > 0 && (
                <div>
                  <p className="text-xs text-gray-400 mb-2">按模型</p>
                  {Object.entries(stats.by_model).map(([model, data]: [string, any]) => (
                    <div key={model} className="flex items-center justify-between text-xs py-1.5 border-b border-gray-100 last:border-0">
                      <span className="font-medium">{model}</span>
                      <span className="text-gray-500">{data.input_tokens.toLocaleString()} / {data.output_tokens.toLocaleString()} tokens</span>
                      <span className="text-green-600">${data.cost?.toFixed(4) || '0'}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : <p className="text-sm text-gray-400">暂无数据</p>}
        </div>

        {/* Context Window 建议 */}
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="font-semibold mb-4">📏 Context Window 建议</h2>
          <div className="flex gap-2 mb-4">
            <input type="number" value={ctxLen} onChange={e => setCtxLen(e.target.value)}
              placeholder="对话长度（消息数）" min="1"
              className="flex-1 px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            <button onClick={handleSuggest} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">建议</button>
          </div>
          {ctxSuggest && (
            <div className="bg-blue-50 p-4 rounded-lg text-sm">
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium">建议窗口:</span>
                <span className="text-lg font-bold text-blue-700">{(ctxSuggest.suggested_window / 1000).toFixed(0)}K</span>
              </div>
              <p className="text-xs text-blue-600">{ctxSuggest.reason}</p>
              <p className="text-xs text-blue-400 mt-1">效率: {ctxSuggest.economy}</p>
            </div>
          )}
        </div>
      </div>

      {/* 功能提示 */}
      <div className="mt-6 bg-gradient-to-r from-blue-50 to-purple-50 border border-blue-100 rounded-xl p-6">
        <h2 className="font-semibold mb-3">✨ 已集成的增强功能</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div className="bg-white/60 p-4 rounded-lg">
            <div className="text-lg mb-1">📊</div>
            <h3 className="font-medium">Token 实时统计</h3>
            <p className="text-xs text-gray-400 mt-1">按模型、按日期统计 Token 使用和费用</p>
          </div>
          <div className="bg-white/60 p-4 rounded-lg">
            <div className="text-lg mb-1">📏</div>
            <h3 className="font-medium">上下文优化</h3>
            <p className="text-xs text-gray-400 mt-1">智能裁剪历史消息，在预算内保留关键信息</p>
          </div>
          <div className="bg-white/60 p-4 rounded-lg">
            <div className="text-lg mb-1">📤</div>
            <h3 className="font-medium">对话导出</h3>
            <p className="text-xs text-gray-400 mt-1">支持 JSON / Markdown 格式导出完整对话</p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ConversationEnhancement
