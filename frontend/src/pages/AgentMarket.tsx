import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  listMarketAgents,
  getMarketAgent,
  installMarketAgent,
  listAgentCategories,
  AgentMarketItem,
  AgentMarketDetail,
} from '../api/agentMarket'
import { useToast } from '../components/ui'

const PAGE_SIZE = 12

const AgentMarket: React.FC = () => {
  const navigate = useNavigate()
  const toast = useToast()
  const [items, setItems] = useState<AgentMarketItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [categories, setCategories] = useState<string[]>([])
  const [activeCategory, setActiveCategory] = useState<string>('')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState<AgentMarketDetail | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)
  const [detailLoading, setDetailLoading] = useState(false)
  const [installOpen, setInstallOpen] = useState(false)
  const [installing, setInstalling] = useState(false)
  const [installName, setInstallName] = useState('')
  const [installConfig, setInstallConfig] = useState<Record<string, any>>({})

  // 加载分类
  useEffect(() => {
    listAgentCategories().then(setCategories).catch(() => {})
  }, [])

  // 加载列表
  useEffect(() => {
    setLoading(true)
    listMarketAgents({ page, page_size: PAGE_SIZE, category: activeCategory || undefined, search: search || undefined })
      .then(res => {
        setItems(res.items)
        setTotal(res.total)
      })
      .catch(() => toast.error('加载失败'))
      .finally(() => setLoading(false))
  }, [page, activeCategory])

  const handleSearch = () => {
    setPage(1)
    setLoading(true)
    listMarketAgents({ page: 1, page_size: PAGE_SIZE, category: activeCategory || undefined, search: search || undefined })
      .then(res => {
        setItems(res.items)
        setTotal(res.total)
      })
      .catch(() => toast.error('搜索失败'))
      .finally(() => setLoading(false))
  }

  const handleViewDetail = async (id: string) => {
    setDetailLoading(true)
    setDetailOpen(true)
    try {
      const detail = await getMarketAgent(id)
      setSelected(detail)
    } catch {
      toast.error('加载详情失败')
      setDetailOpen(false)
    } finally {
      setDetailLoading(false)
    }
  }

  const handleOpenInstall = (item: AgentMarketDetail) => {
    setSelected(item)
    setInstallName(item.name)
    const defaults: Record<string, any> = {}
    if (item.config_schema?.properties) {
      Object.entries(item.config_schema.properties).forEach(([key, prop]: [string, any]) => {
        if (prop.default !== undefined) defaults[key] = prop.default
      })
    }
    setInstallConfig(defaults)
    setInstallOpen(true)
  }

  const handleInstall = async () => {
    if (!selected) return
    setInstalling(true)
    try {
      const resp = await installMarketAgent(selected.id, installConfig, installName)
      toast.success(resp.message || '安装成功')
      setInstallOpen(false)
      const res = await listMarketAgents({ page, page_size: PAGE_SIZE, category: activeCategory || undefined })
      setItems(res.items)
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || '安装失败')
    } finally {
      setInstalling(false)
    }
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* 头部 */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            🧠 Agent 在线市场
          </h1>
          <p className="text-gray-500 mt-1">浏览并一键安装预设的智能体模板</p>
        </div>
        <button
          onClick={() => navigate('/agents')}
          className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 text-sm"
        >
          返回 Agent 管理
        </button>
      </div>

      {/* 搜索栏 */}
      <div className="flex gap-3 mb-4">
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSearch()}
          placeholder="搜索 Agent..."
          className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          onClick={handleSearch}
          className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          搜索
        </button>
      </div>

      {/* 分类筛选 */}
      <div className="flex flex-wrap gap-2 mb-6">
        <button
          onClick={() => setActiveCategory('')}
          className={`px-3 py-1.5 rounded-full text-sm ${activeCategory === '' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
        >
          全部
        </button>
        {categories.map(cat => (
          <button
            key={cat}
            onClick={() => setActiveCategory(cat)}
            className={`px-3 py-1.5 rounded-full text-sm ${activeCategory === cat ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* 加载中 */}
      {loading && (
        <div className="flex justify-center py-12">
          <div className="animate-spin w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full" />
        </div>
      )}

      {/* 列表 */}
      {!loading && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {items.map(item => (
              <div
                key={item.id}
                className="border border-gray-200 rounded-xl p-5 hover:shadow-md transition-shadow bg-white cursor-pointer"
                onClick={() => handleViewDetail(item.id)}
              >
                <div className="flex items-start gap-3 mb-3">
                  <span className="text-3xl">{item.icon}</span>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-lg truncate">{item.name}</h3>
                    <span className="inline-block px-2 py-0.5 bg-gray-100 text-xs text-gray-500 rounded-full mt-1">
                      {item.category}
                    </span>
                  </div>
                </div>
                <p className="text-sm text-gray-600 line-clamp-2 mb-3">{item.description}</p>
                <div className="flex flex-wrap gap-1 mb-3">
                  {item.tags.slice(0, 3).map(tag => (
                    <span key={tag} className="px-2 py-0.5 bg-blue-50 text-blue-600 text-xs rounded-full">
                      {tag}
                    </span>
                  ))}
                </div>
                <div className="flex items-center justify-between text-xs text-gray-400">
                  <span>⭐ {item.rating} · 安装 {item.install_count}</span>
                  <span>v{item.version}</span>
                </div>
              </div>
            ))}
          </div>

          {/* 空状态 */}
          {items.length === 0 && (
            <div className="text-center py-16 text-gray-400">
              <div className="text-5xl mb-4">📦</div>
              <p>暂无匹配的 Agent 模板</p>
            </div>
          )}

          {/* 分页 */}
          {totalPages > 1 && (
            <div className="flex justify-center items-center gap-2 mt-8">
              <button
                disabled={page <= 1}
                onClick={() => setPage(p => Math.max(1, p - 1))}
                className="px-3 py-1.5 border rounded disabled:opacity-30 text-sm"
              >
                上一页
              </button>
              <span className="text-sm text-gray-500">
                第 {page} / {totalPages} 页
              </span>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                className="px-3 py-1.5 border rounded disabled:opacity-30 text-sm"
              >
                下一页
              </button>
            </div>
          )}

          {/* 总数提示 */}
          <p className="text-center text-xs text-gray-400 mt-4">
            共 {total} 个 Agent 模板
          </p>
        </>
      )}

      {/* 详情弹窗 */}
      {detailOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setDetailOpen(false)}>
          <div className="bg-white rounded-2xl w-full max-w-2xl max-h-[85vh] overflow-y-auto m-4" onClick={e => e.stopPropagation()}>
            {detailLoading ? (
              <div className="flex justify-center py-16">
                <div className="animate-spin w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full" />
              </div>
            ) : selected && (
              <>
                {/* 头部 */}
                <div className="p-6 border-b">
                  <div className="flex items-start gap-4">
                    <span className="text-5xl">{selected.icon}</span>
                    <div className="flex-1">
                      <h2 className="text-2xl font-bold">{selected.name}</h2>
                      <div className="flex items-center gap-3 mt-1 text-sm text-gray-500">
                        <span className="px-2 py-0.5 bg-gray-100 rounded-full">{selected.category}</span>
                        <span>v{selected.version}</span>
                        <span>作者: {selected.author}</span>
                      </div>
                      <div className="flex items-center gap-4 mt-2 text-sm">
                        <span className="text-yellow-500">⭐ {selected.rating}</span>
                        <span className="text-gray-400">安装 {selected.install_count}</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* 描述 */}
                <div className="p-6 border-b">
                  <h3 className="font-semibold mb-2">📝 简介</h3>
                  <p className="text-gray-600">{selected.description}</p>
                </div>

                {/* 标签 */}
                <div className="p-6 border-b">
                  <h3 className="font-semibold mb-2">🏷️ 标签</h3>
                  <div className="flex flex-wrap gap-2">
                    {selected.tags.map(tag => (
                      <span key={tag} className="px-3 py-1 bg-blue-50 text-blue-600 rounded-full text-sm">{tag}</span>
                    ))}
                  </div>
                </div>

                {/* 模型配置 */}
                <div className="p-6 border-b">
                  <h3 className="font-semibold mb-3">⚙️ 推荐配置</h3>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div className="bg-gray-50 p-3 rounded-lg">
                      <span className="text-gray-400">模型提供商</span>
                      <p className="font-medium">{selected.model_provider || '-'}</p>
                    </div>
                    <div className="bg-gray-50 p-3 rounded-lg">
                      <span className="text-gray-400">模型名称</span>
                      <p className="font-medium">{selected.model_name || '-'}</p>
                    </div>
                    <div className="bg-gray-50 p-3 rounded-lg">
                      <span className="text-gray-400">Temperature</span>
                      <p className="font-medium">{selected.temperature ?? '-'}</p>
                    </div>
                    <div className="bg-gray-50 p-3 rounded-lg">
                      <span className="text-gray-400">Max Tokens</span>
                      <p className="font-medium">{selected.max_tokens ?? '-'}</p>
                    </div>
                    <div className="bg-gray-50 p-3 rounded-lg">
                      <span className="text-gray-400">Context Window</span>
                      <p className="font-medium">{selected.context_window ?? '-'}</p>
                    </div>
                  </div>
                </div>

                {/* System Prompt */}
                {selected.system_prompt && (
                  <div className="p-6 border-b">
                    <h3 className="font-semibold mb-2">💬 系统提示词</h3>
                    <div className="bg-gray-50 p-4 rounded-lg text-sm text-gray-600 whitespace-pre-wrap">
                      {selected.system_prompt}
                    </div>
                  </div>
                )}

                {/* Welcome Message */}
                {selected.welcome_message && (
                  <div className="p-6 border-b">
                    <h3 className="font-semibold mb-2">👋 欢迎语</h3>
                    <div className="bg-gray-50 p-4 rounded-lg text-sm text-gray-600">
                      {selected.welcome_message}
                    </div>
                  </div>
                )}

                {/* 操作 */}
                <div className="p-6 flex gap-3 justify-end">
                  <button
                    onClick={() => setDetailOpen(false)}
                    className="px-5 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 text-sm"
                  >
                    关闭
                  </button>
                  <button
                    onClick={() => {
                      setDetailOpen(false)
                      handleOpenInstall(selected)
                    }}
                    className="px-5 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm"
                  >
                    安装此 Agent
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* 安装弹窗 */}
      {installOpen && selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setInstallOpen(false)}>
          <div className="bg-white rounded-2xl w-full max-w-lg m-4" onClick={e => e.stopPropagation()}>
            <div className="p-6 border-b">
              <h2 className="text-xl font-bold flex items-center gap-2">
                <span>{selected.icon}</span>
                安装 {selected.name}
              </h2>
            </div>
            <div className="p-6 space-y-4">
              {/* Agent 名称 */}
              {selected.config_schema?.properties?.name && (
                <div>
                  <label className="block text-sm font-medium mb-1">
                    {selected.config_schema.properties.name.title || 'Agent 名称'}
                  </label>
                  <input
                    type="text"
                    value={installName}
                    onChange={e => setInstallName(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  {selected.config_schema.properties.name.description && (
                    <p className="text-xs text-gray-400 mt-1">{selected.config_schema.properties.name.description}</p>
                  )}
                </div>
              )}

              {/* 动态配置字段 */}
              {selected.config_schema?.properties && Object.entries(selected.config_schema.properties)
                .filter(([key]) => key !== 'name')
                .map(([key, prop]: [string, any]) => {
                  if (prop.type === 'number' || prop.type === 'integer') {
                    return (
                      <div key={key}>
                        <label className="block text-sm font-medium mb-1">{prop.title || key}</label>
                        <input
                          type="number"
                          value={installConfig[key] ?? prop.default ?? ''}
                          min={prop.minimum}
                          max={prop.maximum}
                          onChange={e => setInstallConfig(prev => ({ ...prev, [key]: prop.type === 'integer' ? parseInt(e.target.value) || 0 : parseFloat(e.target.value) || 0 }))}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                        {prop.description && <p className="text-xs text-gray-400 mt-1">{prop.description}</p>}
                      </div>
                    )
                  }
                  if (prop.type === 'string') {
                    return (
                      <div key={key}>
                        <label className="block text-sm font-medium mb-1">{prop.title || key}</label>
                        <input
                          type="text"
                          value={installConfig[key] ?? prop.default ?? ''}
                          onChange={e => setInstallConfig(prev => ({ ...prev, [key]: e.target.value }))}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                        {prop.description && <p className="text-xs text-gray-400 mt-1">{prop.description}</p>}
                      </div>
                    )
                  }
                  return null
                })}

              {/* 已启用 Skill */}
              {selected.enabled_skills && selected.enabled_skills.length > 0 && (
                <div className="bg-blue-50 p-3 rounded-lg">
                  <p className="text-sm text-blue-700 font-medium">🔌 将自动启用 {selected.enabled_skills.length} 个 Skill</p>
                </div>
              )}

              {/* 提示 */}
              <div className="bg-yellow-50 p-3 rounded-lg">
                <p className="text-sm text-yellow-700">
                  安装后将自动创建 Agent，可在 Agent 管理页面查看和编辑
                </p>
              </div>
            </div>
            <div className="p-6 border-t flex gap-3 justify-end">
              <button
                onClick={() => setInstallOpen(false)}
                className="px-5 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 text-sm"
                disabled={installing}
              >
                取消
              </button>
              <button
                onClick={handleInstall}
                disabled={installing}
                className="px-5 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm flex items-center gap-2"
              >
                {installing && <div className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" />}
                {installing ? '安装中...' : '确认安装'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default AgentMarket
