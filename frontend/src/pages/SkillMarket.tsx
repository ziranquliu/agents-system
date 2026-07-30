import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loading, Empty } from '../components/ui'
import * as marketApi from '../api/skillMarket'

const categoryIcons: Record<string, string> = {
  '代码': '💻', '数据': '📊', '写作': '✍️', '语言': '🌐', '搜索': '🔍',
  '图像': '🎨', '音频': '🎵', '文件': '📄', '管理': '📋', '知识': '💡',
  '自动化': '⚙️', '通信': '📧', '科学': '🔬', '开发工具': '🛠️', '分析': '📈',
}

export default function SkillMarket() {
  const navigate = useNavigate()
  const [items, setItems] = useState<marketApi.SkillMarketItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [page, setPage] = useState(1)
  const [categories, setCategories] = useState<string[]>([])
  const pageSize = 12

  const [filterCat, setFilterCat] = useState('')
  const [search, setSearch] = useState('')
  const [selectedItem, setSelectedItem] = useState<marketApi.SkillMarketItem | null>(null)
  const [installing, setInstalling] = useState<string | null>(null)

  const fetchItems = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await marketApi.listMarketSkills({
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
    marketApi.listSkillCategories().then(setCategories).catch(() => {})
  }, [])

  const totalPages = Math.ceil(total / pageSize)

  const handleInstall = async (id: string) => {
    setInstalling(id)
    try {
      const result = await marketApi.installMarketSkill(id)
      alert(`✅ ${result.skill.name} 安装成功！`)
      setSelectedItem(null)
      navigate('/skills')
    } catch (e: any) {
      alert(`安装失败: ${e?.message || '未知错误'}`)
    } finally {
      setInstalling(null)
    }
  }

  return (
    <div className="space-y-6">
      {/* 标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">🛒 Skill 在线市场</h1>
          <p className="text-sm text-gray-500 mt-1">浏览并安装预置 Skill 技能包，一键为 Agent 赋能</p>
        </div>
        <span className="text-sm text-gray-500">共 {total} 个 Skill</span>
      </div>

      {/* 搜索栏 */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <div className="flex gap-3">
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && setPage(1)}
            placeholder="搜索 Skill 名称或描述..."
            className="flex-1 text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-400"
          />
          <button onClick={() => setPage(1)} className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700">搜索</button>
        </div>
      </div>

      {/* 分类标签 */}
      <div className="flex flex-wrap gap-2">
        <button onClick={() => { setFilterCat(''); setPage(1) }}
          className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${!filterCat ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
          全部
        </button>
        {categories.map(cat => (
          <button key={cat} onClick={() => { setFilterCat(cat); setPage(1) }}
            className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${filterCat === cat ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
            {categoryIcons[cat] || '📦'} {cat}
          </button>
        ))}
      </div>

      {/* 错误 */}
      {error && <div className="bg-red-50 text-red-600 text-sm px-4 py-3 rounded-lg border border-red-100">{error}</div>}

      {/* 卡片网格 */}
      {loading ? (
        <div className="flex justify-center py-16"><Loading /></div>
      ) : items.length === 0 ? (
        <div className="flex justify-center py-16"><Empty title="没有找到匹配的 Skill" /></div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {items.map(item => (
              <div key={item.id} className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md transition-shadow cursor-pointer"
                onClick={() => setSelectedItem(item)}>
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 rounded-xl bg-blue-50 flex items-center justify-center text-2xl shrink-0">{item.icon || '🧩'}</div>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-gray-900 truncate">{item.name}</h3>
                    <span className="inline-block px-2 py-0.5 mt-1 text-xs rounded-full bg-gray-100 text-gray-600">{item.category}</span>
                  </div>
                </div>
                <p className="mt-3 text-sm text-gray-500 line-clamp-2">{item.description}</p>
                <div className="mt-4 flex items-center justify-between text-xs text-gray-400">
                  <span>⭐ {item.rating || '暂无'} · v{item.version}</span>
                  <span>📥 {item.install_count} 安装</span>
                </div>
              </div>
            ))}
          </div>

          {/* 分页 */}
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

      {/* 详情弹窗 */}
      {selectedItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={() => setSelectedItem(null)}>
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-lg mx-4" onClick={e => e.stopPropagation()}>
            <div className="flex items-start gap-4 mb-4">
              <div className="w-16 h-16 rounded-2xl bg-blue-50 flex items-center justify-center text-3xl shrink-0">{selectedItem.icon || '🧩'}</div>
              <div className="flex-1">
                <h2 className="text-lg font-semibold text-gray-900">{selectedItem.name}</h2>
                <div className="flex items-center gap-3 mt-1">
                  <span className="px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-600">{selectedItem.category}</span>
                  <span className="text-xs text-gray-400">v{selectedItem.version}</span>
                  <span className="text-xs text-gray-400">作者: {selectedItem.author}</span>
                </div>
              </div>
            </div>
            <p className="text-sm text-gray-600 mb-4">{selectedItem.description}</p>
            <div className="flex flex-wrap gap-1.5 mb-4">
              {selectedItem.tags.map(t => (
                <span key={t} className="px-2 py-0.5 text-xs rounded-full bg-blue-50 text-blue-600">{t}</span>
              ))}
            </div>
            <div className="flex items-center justify-between text-sm text-gray-500 mb-5">
              <span>⭐ {selectedItem.rating || '暂无评分'} · 📥 {selectedItem.install_count} 次安装</span>
            </div>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setSelectedItem(null)}
                className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">关闭</button>
              <button onClick={() => handleInstall(selectedItem.id)} disabled={installing === selectedItem.id}
                className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-50">
                {installing === selectedItem.id ? '安装中...' : '📥 安装此 Skill'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
