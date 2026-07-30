import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  listMarketModels,
  getMarketModel,
  installMarketModel,
  listModelCategories,
  ModelMarketItem,
} from '../api/modelMarket'
import { useToast } from '../components/ui'

const PAGE_SIZE = 12

const ModelMarket: React.FC = () => {
  const navigate = useNavigate()
  const toast = useToast()
  const [items, setItems] = useState<ModelMarketItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [categories, setCategories] = useState<string[]>([])
  const [activeCategory, setActiveCategory] = useState<string>('')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState<ModelMarketItem | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)
  const [detailLoading, setDetailLoading] = useState(false)
  const [installOpen, setInstallOpen] = useState(false)
  const [installing, setInstalling] = useState(false)
  const [installName, setInstallName] = useState('')
  const [installConfig, setInstallConfig] = useState<Record<string, any>>({})

  useEffect(() => {
    listModelCategories().then(setCategories).catch(() => {})
  }, [])

  useEffect(() => {
    setLoading(true)
    listMarketModels({ page, page_size: PAGE_SIZE, category: activeCategory || undefined, search: search || undefined })
      .then(res => { setItems(res.items); setTotal(res.total) })
      .catch(() => toast.error('加载失败'))
      .finally(() => setLoading(false))
  }, [page, activeCategory])

  const handleSearch = () => {
    setPage(1)
    setLoading(true)
    listMarketModels({ page: 1, page_size: PAGE_SIZE, category: activeCategory || undefined, search: search || undefined })
      .then(res => { setItems(res.items); setTotal(res.total) })
      .catch(() => toast.error('搜索失败'))
      .finally(() => setLoading(false))
  }

  const handleViewDetail = async (id: string) => {
    setDetailLoading(true)
    setDetailOpen(true)
    try {
      const detail = await getMarketModel(id)
      setSelected(detail)
    } catch {
      toast.error('加载详情失败')
      setDetailOpen(false)
    } finally {
      setDetailLoading(false)
    }
  }

  const handleOpenInstall = (item: ModelMarketItem) => {
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
      const resp = await installMarketModel(selected.id, installConfig, installName)
      toast.success(resp.message || '配置成功')
      setInstallOpen(false)
      const res = await listMarketModels({ page, page_size: PAGE_SIZE, category: activeCategory || undefined })
      setItems(res.items)
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || '配置失败')
    } finally {
      setInstalling(false)
    }
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)

  const featureLabels: Record<string, string> = {
    chat: '文本对话',
    vision: '图像识别',
    audio: '音频理解',
    video: '视频理解',
    'function-calling': '函数调用',
    streaming: '流式输出',
    'json-mode': 'JSON 模式',
    'extended-thinking': '深度思考',
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* 头部 */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            🧠 模型在线市场
          </h1>
          <p className="text-gray-500 mt-1">浏览推荐的 AI 模型并一键配置到系统中</p>
        </div>
        <button
          onClick={() => navigate('/models')}
          className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 text-sm"
        >
          返回模型管理
        </button>
      </div>

      {/* 搜索栏 */}
      <div className="flex gap-3 mb-4">
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSearch()}
          placeholder="搜索模型..."
          className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button onClick={handleSearch} className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">搜索</button>
      </div>

      {/* 分类 */}
      <div className="flex flex-wrap gap-2 mb-6">
        <button
          onClick={() => setActiveCategory('')}
          className={`px-3 py-1.5 rounded-full text-sm ${activeCategory === '' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
        >全部</button>
        {categories.map(cat => (
          <button
            key={cat}
            onClick={() => setActiveCategory(cat)}
            className={`px-3 py-1.5 rounded-full text-sm ${activeCategory === cat ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
          >{cat}</button>
        ))}
      </div>

      {/* 加载 */}
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
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-xs text-gray-400">{item.provider}</span>
                      <span className="px-1.5 py-0.5 bg-gray-100 text-xs text-gray-500 rounded-full">{item.category}</span>
                    </div>
                  </div>
                </div>
                <p className="text-sm text-gray-600 line-clamp-2 mb-3">{item.description}</p>
                {/* 特性标签 */}
                {item.features && item.features.length > 0 && (
                  <div className="flex flex-wrap gap-1 mb-3">
                    {item.features.slice(0, 4).map(f => (
                      <span key={f} className="px-2 py-0.5 bg-green-50 text-green-600 text-xs rounded-full">
                        {featureLabels[f] || f}
                      </span>
                    ))}
                  </div>
                )}
                {/* 价格 */}
                <div className="flex items-center justify-between text-xs text-gray-400">
                  {item.pricing ? (
                    <span>
                      {item.pricing.input === 0 ? '免费' :
                        `$${item.pricing.input}/${item.pricing.unit || '1M tokens'}`
                      }
                    </span>
                  ) : <span />}
                  <span>{item.context_window ? `${(item.context_window / 1000).toFixed(0)}K 上下文` : ''}</span>
                </div>
                <div className="flex items-center justify-between mt-1 text-xs text-gray-400">
                  <span>⭐ {item.rating} · 配置 {item.install_count}</span>
                  <span>v{item.version}</span>
                </div>
              </div>
            ))}
          </div>

          {items.length === 0 && (
            <div className="text-center py-16 text-gray-400">
              <div className="text-5xl mb-4">📦</div>
              <p>暂无匹配的模型推荐</p>
            </div>
          )}

          {totalPages > 1 && (
            <div className="flex justify-center items-center gap-2 mt-8">
              <button disabled={page <= 1} onClick={() => setPage(p => Math.max(1, p - 1))} className="px-3 py-1.5 border rounded disabled:opacity-30 text-sm">上一页</button>
              <span className="text-sm text-gray-500">第 {page} / {totalPages} 页</span>
              <button disabled={page >= totalPages} onClick={() => setPage(p => Math.min(totalPages, p + 1))} className="px-3 py-1.5 border rounded disabled:opacity-30 text-sm">下一页</button>
            </div>
          )}

          <p className="text-center text-xs text-gray-400 mt-4">共 {total} 个模型推荐</p>
        </>
      )}

      {/* 详情弹窗 */}
      {detailOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setDetailOpen(false)}>
          <div className="bg-white rounded-2xl w-full max-w-2xl max-h-[85vh] overflow-y-auto m-4" onClick={e => e.stopPropagation()}>
            {detailLoading ? (
              <div className="flex justify-center py-16"><div className="animate-spin w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full" /></div>
            ) : selected && (
              <>
                <div className="p-6 border-b">
                  <div className="flex items-start gap-4">
                    <span className="text-5xl">{selected.icon}</span>
                    <div className="flex-1">
                      <h2 className="text-2xl font-bold">{selected.name}</h2>
                      <div className="flex items-center gap-3 mt-1 text-sm text-gray-500">
                        <span>{selected.provider}</span>
                        <span className="px-2 py-0.5 bg-gray-100 rounded-full">{selected.category}</span>
                        <span>v{selected.version}</span>
                      </div>
                      <div className="flex items-center gap-4 mt-2 text-sm">
                        <span className="text-yellow-500">⭐ {selected.rating}</span>
                        <span className="text-gray-400">配置 {selected.install_count}</span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="p-6 border-b">
                  <h3 className="font-semibold mb-2">📝 简介</h3>
                  <p className="text-gray-600">{selected.description}</p>
                </div>

                <div className="p-6 border-b">
                  <h3 className="font-semibold mb-3">⚙️ 模型信息</h3>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div className="bg-gray-50 p-3 rounded-lg">
                      <span className="text-gray-400">提供商</span>
                      <p className="font-medium">{selected.provider}</p>
                    </div>
                    <div className="bg-gray-50 p-3 rounded-lg">
                      <span className="text-gray-400">模型名称</span>
                      <p className="font-medium font-mono text-xs break-all">{selected.model_name || '-'}</p>
                    </div>
                    <div className="bg-gray-50 p-3 rounded-lg">
                      <span className="text-gray-400">API 地址</span>
                      <p className="font-medium font-mono text-xs break-all">{selected.api_base || '-'}</p>
                    </div>
                    <div className="bg-gray-50 p-3 rounded-lg">
                      <span className="text-gray-400">上下文窗口</span>
                      <p className="font-medium">{selected.context_window ? `${(selected.context_window / 1000).toFixed(0)}K tokens` : '-'}</p>
                    </div>
                    <div className="bg-gray-50 p-3 rounded-lg">
                      <span className="text-gray-400">最大输出</span>
                      <p className="font-medium">{selected.max_tokens ? `${selected.max_tokens} tokens` : '-'}</p>
                    </div>
                    <div className="bg-gray-50 p-3 rounded-lg">
                      <span className="text-gray-400">价格</span>
                      <p className="font-medium">{selected.pricing ? (selected.pricing.input === 0 ? '免费' : `$${selected.pricing.input}/${selected.pricing.unit || '1M'}`) : '-'}</p>
                    </div>
                  </div>
                </div>

                <div className="p-6 border-b">
                  <h3 className="font-semibold mb-2">🔌 支持功能</h3>
                  <div className="flex flex-wrap gap-2">
                    {selected.features?.map(f => (
                      <span key={f} className="px-3 py-1 bg-green-50 text-green-600 rounded-full text-sm">{featureLabels[f] || f}</span>
                    )) || <span className="text-gray-400 text-sm">无特殊功能标注</span>}
                  </div>
                </div>

                <div className="p-6 flex gap-3 justify-end">
                  <button onClick={() => setDetailOpen(false)} className="px-5 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 text-sm">关闭</button>
                  <button
                    onClick={() => { setDetailOpen(false); handleOpenInstall(selected) }}
                    className="px-5 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm"
                  >
                    配置此模型
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* 安装/配置弹窗 */}
      {installOpen && selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setInstallOpen(false)}>
          <div className="bg-white rounded-2xl w-full max-w-lg m-4" onClick={e => e.stopPropagation()}>
            <div className="p-6 border-b">
              <h2 className="text-xl font-bold flex items-center gap-2">
                <span>{selected.icon}</span>
                配置 {selected.name}
              </h2>
            </div>
            <div className="p-6 space-y-4">
              {selected.config_schema?.properties?.name && (
                <div>
                  <label className="block text-sm font-medium mb-1">{selected.config_schema.properties.name.title || '配置名称'}</label>
                  <input type="text" value={installName} onChange={e => setInstallName(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" />
                  {selected.config_schema.properties.name.description &&
                    <p className="text-xs text-gray-400 mt-1">{selected.config_schema.properties.name.description}</p>}
                </div>
              )}

              {selected.config_schema?.properties && Object.entries(selected.config_schema.properties)
                .filter(([key]) => key !== 'name')
                .map(([key, prop]: [string, any]) => {
                  if (prop.type === 'number' || prop.type === 'integer') {
                    return (
                      <div key={key}>
                        <label className="block text-sm font-medium mb-1">{prop.title || key}</label>
                        <input type="number" value={installConfig[key] ?? prop.default ?? ''}
                          min={prop.minimum} max={prop.maximum}
                          onChange={e => setInstallConfig(prev => ({ ...prev, [key]: prop.type === 'integer' ? parseInt(e.target.value) || 0 : parseFloat(e.target.value) || 0 }))}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" />
                        {prop.description && <p className="text-xs text-gray-400 mt-1">{prop.description}</p>}
                      </div>
                    )
                  }
                  // api_key uses password input
                  if (key === 'api_key') {
                    return (
                      <div key={key}>
                        <label className="block text-sm font-medium mb-1">{prop.title || 'API Key'} {prop.required && <span className="text-red-500">*</span>}</label>
                        <input type="password" value={installConfig[key] ?? ''}
                          placeholder="输入 API Key"
                          onChange={e => setInstallConfig(prev => ({ ...prev, [key]: e.target.value }))}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" />
                        {prop.description && <p className="text-xs text-gray-400 mt-1">{prop.description}</p>}
                      </div>
                    )
                  }
                  if (prop.type === 'string') {
                    return (
                      <div key={key}>
                        <label className="block text-sm font-medium mb-1">{prop.title || key}</label>
                        <input type="text" value={installConfig[key] ?? prop.default ?? ''}
                          placeholder={prop.default ? '' : `输入${prop.title || key}`}
                          onChange={e => setInstallConfig(prev => ({ ...prev, [key]: e.target.value }))}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" />
                        {prop.description && <p className="text-xs text-gray-400 mt-1">{prop.description}</p>}
                      </div>
                    )
                  }
                  return null
                })}

              <div className="bg-yellow-50 p-3 rounded-lg">
                <p className="text-sm text-yellow-700">
                  配置后将在模型管理中创建一条记录，可在模型管理页面修改或删除
                </p>
              </div>
            </div>
            <div className="p-6 border-t flex gap-3 justify-end">
              <button onClick={() => setInstallOpen(false)} className="px-5 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 text-sm" disabled={installing}>取消</button>
              <button
                onClick={handleInstall}
                disabled={installing}
                className="px-5 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm flex items-center gap-2"
              >
                {installing && <div className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" />}
                {installing ? '配置中...' : '确认配置'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ModelMarket
