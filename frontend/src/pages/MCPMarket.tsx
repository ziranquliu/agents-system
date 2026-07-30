import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loading, Empty } from '../components/ui'
import * as marketApi from '../api/mcpMarket'

const categoryIcons: Record<string, string> = {
  '数据库': '🗄️', '搜索': '🔍', '代码执行': '⚡', '网络': '🌐',
  'AI 服务': '🤖', '云服务': '☁️', '运维': '🐳', '通信': '📨',
  '文件系统': '📁', '开发工具': '🛠️',
}

const protocolColors: Record<string, string> = {
  stdio: 'bg-green-100 text-green-700',
  sse: 'bg-blue-100 text-blue-700',
}

export default function MCPMarket() {
  const navigate = useNavigate()
  const [items, setItems] = useState<marketApi.MCPMarketItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [page, setPage] = useState(1)
  const [categories, setCategories] = useState<string[]>([])
  const pageSize = 12

  const [filterCat, setFilterCat] = useState('')
  const [search, setSearch] = useState('')
  const [selectedItem, setSelectedItem] = useState<marketApi.MCPMarketItem | null>(null)
  const [installing, setInstalling] = useState(false)
  const [installName, setInstallName] = useState('')
  const [installConfig, setInstallConfig] = useState<Record<string, any>>({})

  const fetchItems = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await marketApi.listMarketMCP({
        page, page_size: pageSize,
        category: filterCat || undefined,
        search: search || undefined,
      })
      setItems(data.items)
      setTotal(data.total)
    } catch {
      setError('加载失败')
    } finally {
      setLoading(false)
    }
  }, [page, filterCat, search])

  useEffect(() => { fetchItems() }, [fetchItems])
  useEffect(() => {
    marketApi.listMCPCategories().then(setCategories).catch(() => {})
  }, [])

  const totalPages = Math.ceil(total / pageSize)

  const openInstall = (item: marketApi.MCPMarketItem) => {
    setSelectedItem(item)
    setInstallName(item.name)
    setInstallConfig({})
  }

  const handleInstall = async () => {
    if (!selectedItem) return
    setInstalling(true)
    try {
      await marketApi.installMarketMCP(selectedItem.id, installConfig, installName)
      alert('✅ MCP 服务安装成功！')
      setSelectedItem(null)
      navigate('/mcp-servers')
    } catch (e: any) {
      alert(`安装失败: ${e?.message || '未知错误'}`)
    } finally {
      setInstalling(false)
    }
  }

  const renderConfigField = (key: string, prop: any) => {
    const value = installConfig[key] ?? prop.default ?? ''
    const handleChange = (v: any) => setInstallConfig(prev => ({ ...prev, [key]: v }))

    if (prop.enum) {
      return (
        <select key={key} value={value} onChange={e => handleChange(e.target.value)}
          className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-400">
          {prop.enum.map((opt: string) => <option key={opt} value={opt}>{opt}</option>)}
        </select>
      )
    }
    if (prop.type === 'boolean') {
      return (
        <label key={key} className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={value === true} onChange={e => handleChange(e.target.checked)}
            className="w-4 h-4 rounded border-gray-300 text-blue-600" />
          {prop.description || key}
        </label>
      )
    }
    if (prop.type === 'number') {
      return (
        <input key={key} type="number" value={value} onChange={e => handleChange(Number(e.target.value))}
          placeholder={prop.description || key}
          className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-400" />
      )
    }
    const inputType = key.includes('password') || key.includes('secret') || key.includes('key') ? 'password' : 'text'
    return (
      <input key={key} type={inputType} value={value} onChange={e => handleChange(e.target.value)}
        placeholder={prop.description || key}
        className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-400" />
    )
  }

  return (
    <div className="space-y-6">
      {/* 标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">🛒 MCP 在线市场</h1>
          <p className="text-sm text-gray-500 mt-1">选择预置 MCP 服务模板，一键接入外部工具和数据库</p>
        </div>
        <span className="text-sm text-gray-500">共 {total} 个服务</span>
      </div>

      {/* 搜索 */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <div className="flex gap-3">
          <input value={search} onChange={e => setSearch(e.target.value)} onKeyDown={e => e.key === 'Enter' && setPage(1)}
            placeholder="搜索 MCP 服务..."
            className="flex-1 text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-400" />
          <button onClick={() => setPage(1)} className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700">搜索</button>
        </div>
      </div>

      {/* 分类 */}
      <div className="flex flex-wrap gap-2">
        <button onClick={() => { setFilterCat(''); setPage(1) }}
          className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${!filterCat ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>全部</button>
        {categories.map(cat => (
          <button key={cat} onClick={() => { setFilterCat(cat); setPage(1) }}
            className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${filterCat === cat ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
            {categoryIcons[cat] || '📦'} {cat}
          </button>
        ))}
      </div>

      {error && <div className="bg-red-50 text-red-600 text-sm px-4 py-3 rounded-lg border border-red-100">{error}</div>}

      {loading ? (
        <div className="flex justify-center py-16"><Loading /></div>
      ) : items.length === 0 ? (
        <div className="flex justify-center py-16"><Empty title="没有找到匹配的 MCP 服务" /></div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {items.map(item => (
              <div key={item.id}
                className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md transition-shadow cursor-pointer"
                onClick={() => openInstall(item)}>
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 rounded-xl bg-purple-50 flex items-center justify-center text-2xl shrink-0">{item.icon || '🔌'}</div>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-gray-900 truncate">{item.name}</h3>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-600">{item.category}</span>
                      <span className={`px-2 py-0.5 text-xs rounded-full ${protocolColors[item.protocol] || 'bg-gray-100 text-gray-600'}`}>
                        {item.protocol}
                      </span>
                    </div>
                  </div>
                </div>
                <p className="mt-3 text-sm text-gray-500 line-clamp-2">{item.description}</p>
                <div className="mt-4 flex items-center justify-between text-xs text-gray-400">
                  <span>v{item.version} · {item.author}</span>
                  <span>📥 {item.install_count} 安装</span>
                </div>
              </div>
            ))}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between bg-white rounded-xl border border-gray-200 px-4 py-3">
              <span className="text-sm text-gray-500">第 {page}/{totalPages} 页</span>
              <div className="flex gap-2">
                <button onClick={() => setPage(p => Math.max(1, p-1))} disabled={page<=1}
                  className="px-3 py-1 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50">上一页</button>
                <button onClick={() => setPage(p => Math.min(totalPages, p+1))} disabled={page>=totalPages}
                  className="px-3 py-1 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50">下一页</button>
              </div>
            </div>
          )}
        </>
      )}

      {/* 安装弹窗 */}
      {selectedItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={() => setSelectedItem(null)}>
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-lg mx-4" onClick={e => e.stopPropagation()}>
            <div className="flex items-start gap-4 mb-4">
              <div className="w-14 h-14 rounded-2xl bg-purple-50 flex items-center justify-center text-2xl shrink-0">{selectedItem.icon || '🔌'}</div>
              <div className="flex-1">
                <h2 className="text-lg font-semibold text-gray-900">{selectedItem.name}</h2>
                <div className="flex items-center gap-2 mt-1">
                  <span className="px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-600">{selectedItem.category}</span>
                  <span className={`px-2 py-0.5 text-xs rounded-full ${protocolColors[selectedItem.protocol] || ''}`}>{selectedItem.protocol}</span>
                  <span className="text-xs text-gray-400">v{selectedItem.version}</span>
                </div>
              </div>
            </div>
            <p className="text-sm text-gray-600 mb-4">{selectedItem.description}</p>

            {/* 配置表单 */}
            <div className="space-y-3 mb-5">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">服务名称</label>
                <input value={installName} onChange={e => setInstallName(e.target.value)}
                  className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-400" />
              </div>
              {(() => {
                const schema = selectedItem.config_schema || {}
                const props = schema.properties || {}
                return Object.entries(props).map(([key, prop]: [string, any]) => (
                  <div key={key}>
                    <label className="block text-xs font-medium text-gray-600 mb-1">
                      {prop.description || key}
                      {(schema.required || []).includes(key) && <span className="text-red-500 ml-1">*</span>}
                    </label>
                    {renderConfigField(key, prop)}
                  </div>
                ))
              })()}
            </div>

            <div className="flex gap-2 justify-end">
              <button onClick={() => setSelectedItem(null)}
                className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">取消</button>
              <button onClick={handleInstall} disabled={installing}
                className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-50">
                {installing ? '安装中...' : '🔌 一键接入'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
