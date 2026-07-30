import React, { useEffect, useState } from 'react'
import { getPoolStats, getLoadBalancer, getSecurityConfig, setLoadBalancerServers, updateSecurityConfig, resetCircuitBreaker } from '../api/mcpOptimization'
import { listMCPServers } from '../api/mcps'
import { useToast } from '../components/ui'

const MCPOptimization: React.FC = () => {
  const toast = useToast()
  const [pool, setPool] = useState<any>(null)
  const [lb, setLb] = useState<any>(null)
  const [security, setSecurity] = useState<any>(null)
  const [servers, setServers] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [lbServerInput, setLbServerInput] = useState('')

  const loadData = async () => {
    setLoading(true)
    try {
      const [p, l, s, sv] = await Promise.all([
        getPoolStats(), getLoadBalancer(), getSecurityConfig(), listMCPServers(),
      ])
      setPool(p)
      setLb(l)
      setSecurity(s)
      setServers(sv.items || [])
    } catch { toast.error('加载数据失败') }
    finally { setLoading(false) }
  }

  useEffect(() => { loadData() }, [])

  const handleSetLbServers = async () => {
    const ids = lbServerInput.split(',').map(s => s.trim()).filter(Boolean)
    if (!ids.length) { toast.error('请输入 Server ID'); return }
    try {
      const resp = await setLoadBalancerServers(ids)
      setLb((prev: any) => ({ ...prev, servers: resp.servers }))
      toast.success('负载均衡服务器已更新')
    } catch { toast.error('更新失败') }
  }

  const handleResetCB = async (serverId: string) => {
    try {
      await resetCircuitBreaker(serverId)
      toast.success('熔断器已重置')
    } catch { toast.error('重置失败') }
  }

  const handleUpdateSecurity = async (key: string, value: any) => {
    try {
      const resp = await updateSecurityConfig({ [key]: value })
      setSecurity(resp.config)
      toast.success('安全配置已更新')
    } catch { toast.error('更新失败') }
  }

  if (loading) return <div className="flex justify-center py-16"><div className="animate-spin w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full" /></div>

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <h1 className="text-2xl font-bold flex items-center gap-2 mb-6">🔌 MCP 使用优化</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 连接池 */}
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="font-semibold mb-4">🔗 连接池</h2>
          {pool && (
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="bg-gray-50 p-3 rounded-lg"><span className="text-gray-400">最大池大小</span><p className="font-medium">{pool.max_pool_size}</p></div>
              <div className="bg-gray-50 p-3 rounded-lg"><span className="text-gray-400">活跃连接</span><p className="font-medium">{pool.active_connections}</p></div>
              <div className="bg-gray-50 p-3 rounded-lg"><span className="text-gray-400">总连接数</span><p className="font-medium">{pool.total_connections}</p></div>
              <div className="bg-gray-50 p-3 rounded-lg"><span className="text-gray-400">创建时间</span><p className="font-medium text-xs">{pool.created_at?.slice(0, 19) || '-'}</p></div>
            </div>
          )}
        </div>

        {/* 熔断器 */}
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="font-semibold mb-4">🛡️ 熔断器</h2>
          <div className="divide-y">
            {servers.length === 0 ? (
              <p className="text-sm text-gray-400">暂无 MCP 服务器</p>
            ) : (
              servers.map(s => (
                <div key={s.id} className="py-2 flex items-center justify-between">
                  <div>
                    <span className="text-sm font-medium">{s.name}</span>
                    <span className="text-xs text-gray-400 ml-2">{s.url}</span>
                  </div>
                  <button onClick={() => handleResetCB(s.id)} className="px-3 py-1 bg-red-50 text-red-600 rounded text-xs hover:bg-red-100">重置</button>
                </div>
              ))
            )}
          </div>
        </div>

        {/* 负载均衡 */}
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="font-semibold mb-4">⚖️ 负载均衡</h2>
          <div className="mb-3 text-sm">
            <span className="text-gray-400">策略: </span>
            <span className="font-medium">{lb?.strategy || 'round-robin'} · </span>
            <span className="text-gray-400">可用服务器: </span>
            <span className="font-medium">{lb?.available || 0}</span>
          </div>
          {lb?.servers?.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-3">
              {lb.servers.map((s: string) => (
                <span key={s} className="px-2 py-1 bg-blue-50 text-blue-600 rounded text-xs">{s}</span>
              ))}
            </div>
          )}
          <div className="flex gap-2">
            <input type="text" value={lbServerInput} onChange={e => setLbServerInput(e.target.value)}
              placeholder="Server IDs (逗号分隔)" className="flex-1 px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            <button onClick={handleSetLbServers} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">更新</button>
          </div>
        </div>

        {/* 安全配置 */}
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="font-semibold mb-4">🔐 安全配置</h2>
          {security && (
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-gray-400">TLS 加密</span>
                <button
                  onClick={() => handleUpdateSecurity('tls_enabled', !security.tls_enabled)}
                  className={`px-3 py-1 rounded text-xs font-medium ${security.tls_enabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}
                >
                  {security.tls_enabled ? '已启用' : '已关闭'}
                </button>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-400">API Key 验证</span>
                <button
                  onClick={() => handleUpdateSecurity('api_key_required', !security.api_key_required)}
                  className={`px-3 py-1 rounded text-xs font-medium ${security.api_key_required ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}
                >
                  {security.api_key_required ? '已启用' : '已关闭'}
                </button>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-400">速率限制</span>
                <span className="font-medium">{security.rate_limit_per_minute}/分钟</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-400">最大请求体</span>
                <span className="font-medium">{security.max_request_size_mb} MB</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default MCPOptimization
