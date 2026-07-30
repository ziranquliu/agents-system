import React, { useEffect, useState } from 'react'
import { listKnowledgeBases, createKnowledgeBase, getDocuments, addDocument, deleteDocument, searchKnowledge, KnowledgeBase, KnowledgeDocument, SearchResult } from '../api/knowledge'
import { useToast } from '../components/ui'

const KnowledgePage: React.FC = () => {
  const toast = useToast()
  const [kbs, setKbs] = useState<KnowledgeBase[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [selectedKb, setSelectedKb] = useState<KnowledgeBase | null>(null)
  const [docs, setDocs] = useState<KnowledgeDocument[]>([])
  const [createOpen, setCreateOpen] = useState(false)
  const [addDocOpen, setAddDocOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [searching, setSearching] = useState(false)

  // 创建表单
  const [formName, setFormName] = useState('')
  const [formDesc, setFormDesc] = useState('')
  const [formIcon, setFormIcon] = useState('📚')

  // 添加文档
  const [docTitle, setDocTitle] = useState('')
  const [docContent, setDocContent] = useState('')

  const loadKbs = async () => {
    setLoading(true)
    try {
      const data = await listKnowledgeBases(1, 50)
      setKbs(data.items)
      setTotal(data.total)
    } catch { toast.error('加载知识库失败') }
    finally { setLoading(false) }
  }

  useEffect(() => { loadKbs() }, [])

  const handleSelectKb = async (kb: KnowledgeBase) => {
    setSelectedKb(kb)
    try {
      const data = await getDocuments(kb.id)
      setDocs(data.items)
    } catch { toast.error('加载文档失败') }
  }

  const handleCreate = async () => {
    if (!formName.trim()) { toast.error('请输入名称'); return }
    try {
      await createKnowledgeBase(formName, formDesc, formIcon)
      toast.success('知识库已创建')
      setCreateOpen(false)
      setFormName(''); setFormDesc('')
      loadKbs()
    } catch { toast.error('创建失败') }
  }

  const handleAddDoc = async () => {
    if (!selectedKb || !docTitle.trim() || !docContent.trim()) { toast.error('请填写完整信息'); return }
    try {
      await addDocument(selectedKb.id, docTitle, docContent)
      toast.success('文档已添加')
      setAddDocOpen(false)
      setDocTitle(''); setDocContent('')
      const data = await getDocuments(selectedKb.id)
      setDocs(data.items)
      loadKbs()
    } catch { toast.error('添加失败') }
  }

  const handleDeleteDoc = async (docId: string) => {
    if (!selectedKb) return
    try {
      await deleteDocument(selectedKb.id, docId)
      toast.success('文档已删除')
      const data = await getDocuments(selectedKb.id)
      setDocs(data.items)
      loadKbs()
    } catch { toast.error('删除失败') }
  }

  const handleSearch = async () => {
    if (!selectedKb || !query.trim()) return
    setSearching(true)
    try {
      const data = await searchKnowledge(selectedKb.id, query)
      setSearchResults(data.results)
    } catch { toast.error('搜索失败') }
    finally { setSearching(false) }
  }

  const icons = ['📚', '📖', '📕', '📗', '📘', '📙', '📓', '📔', '📒', '📑']

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">📚 知识库管理</h1>
          <p className="text-gray-500 mt-1">创建和管理知识库，添加文档并检索</p>
        </div>
        <button onClick={() => setCreateOpen(true)} className="px-5 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm">创建知识库</button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 知识库列表 */}
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b bg-gray-50 font-semibold text-sm">知识库 ({total})</div>
          {loading ? (
            <div className="flex justify-center py-8"><div className="animate-spin w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full" /></div>
          ) : kbs.length === 0 ? (
            <div className="text-center py-8 text-gray-400 text-sm">暂无知识库</div>
          ) : (
            <div className="divide-y">
              {kbs.map(kb => (
                <div key={kb.id} onClick={() => handleSelectKb(kb)}
                  className={`px-4 py-3 cursor-pointer hover:bg-gray-50 ${selectedKb?.id === kb.id ? 'bg-blue-50 border-l-2 border-blue-500' : ''}`}>
                  <div className="flex items-center gap-2">
                    <span>{kb.icon}</span>
                    <span className="font-medium text-sm">{kb.name}</span>
                  </div>
                  <div className="text-xs text-gray-400 mt-1">{kb.document_count} 文档 · {kb.chunk_count} 块</div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 文档列表 / 搜索 */}
        <div className="lg:col-span-2">
          {selectedKb ? (
            <div className="bg-white border border-gray-200 rounded-xl">
              {/* 头部 */}
              <div className="px-5 py-3 border-b bg-gray-50 flex items-center justify-between">
                <h3 className="font-semibold text-sm">{selectedKb.icon} {selectedKb.name} - 文档</h3>
                <button onClick={() => setAddDocOpen(true)} className="px-3 py-1.5 bg-blue-600 text-white rounded text-xs hover:bg-blue-700">添加文档</button>
              </div>

              {/* 搜索栏 */}
              <div className="px-5 py-3 border-b flex gap-2">
                <input type="text" value={query} onChange={e => setQuery(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleSearch()}
                  placeholder="搜索知识库内容..." className="flex-1 px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                <button onClick={handleSearch} disabled={searching} className="px-4 py-2 bg-gray-600 text-white rounded-lg text-sm hover:bg-gray-700 disabled:opacity-50">
                  {searching ? '搜索中...' : '搜索'}
                </button>
              </div>

              {/* 搜索结果 */}
              {searchResults.length > 0 && (
                <div className="px-5 py-3 border-b bg-yellow-50">
                  <p className="text-xs text-yellow-700 mb-2">搜索结果 ({searchResults.length})</p>
                  {searchResults.map(r => (
                    <div key={r.chunk_id} className="text-xs bg-white p-2 rounded mb-1 border border-yellow-100">
                      <p className="text-gray-600">{r.content.slice(0, 200)}...</p>
                      <p className="text-gray-400 mt-0.5">得分: {r.score} · Token: {r.token_count}</p>
                    </div>
                  ))}
                </div>
              )}

              {/* 文档列表 */}
              <div className="divide-y max-h-[50vh] overflow-y-auto">
                {docs.length === 0 ? (
                  <div className="text-center py-12 text-gray-400 text-sm">暂无文档</div>
                ) : (
                  docs.map(doc => (
                    <div key={doc.id} className="px-5 py-4">
                      <div className="flex items-start justify-between">
                        <div>
                          <h4 className="font-medium text-sm">{doc.title}</h4>
                          <p className="text-xs text-gray-400 mt-0.5">
                            {doc.content_type} · {(doc.file_size || 0) > 1024 ? `${((doc.file_size || 0) / 1024).toFixed(1)}KB` : `${doc.file_size || 0}B`}
                            · {doc.chunk_count} 块 · {doc.created_at ? new Date(doc.created_at).toLocaleString() : ''}
                          </p>
                          {doc.content && <p className="text-xs text-gray-500 mt-1 line-clamp-2">{doc.content}</p>}
                        </div>
                        <button onClick={() => handleDeleteDoc(doc.id)} className="px-2 py-1 text-red-400 hover:text-red-600 text-xs">删除</button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          ) : (
            <div className="bg-white border border-gray-200 rounded-xl flex items-center justify-center py-16 text-gray-400">
              <div className="text-center">
                <div className="text-5xl mb-4">📚</div>
                <p>选择一个知识库查看文档</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 创建知识库弹窗 */}
      {createOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setCreateOpen(false)}>
          <div className="bg-white rounded-2xl w-full max-w-md m-4 p-6" onClick={e => e.stopPropagation()}>
            <h2 className="text-xl font-bold mb-4">创建知识库</h2>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium mb-1">图标</label>
                <div className="flex gap-2 flex-wrap">
                  {icons.map(ic => (
                    <button key={ic} onClick={() => setFormIcon(ic)}
                      className={`w-9 h-9 rounded-lg border ${formIcon === ic ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:bg-gray-50'}`}>{ic}</button>
                  ))}
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">名称 *</label>
                <input type="text" value={formName} onChange={e => setFormName(e.target.value)} className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">描述</label>
                <textarea value={formDesc} onChange={e => setFormDesc(e.target.value)} rows={3} className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
            </div>
            <div className="flex gap-3 justify-end mt-6">
              <button onClick={() => setCreateOpen(false)} className="px-4 py-2 border rounded-lg text-sm">取消</button>
              <button onClick={handleCreate} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm">创建</button>
            </div>
          </div>
        </div>
      )}

      {/* 添加文档弹窗 */}
      {addDocOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setAddDocOpen(false)}>
          <div className="bg-white rounded-2xl w-full max-w-lg m-4 p-6" onClick={e => e.stopPropagation()}>
            <h2 className="text-xl font-bold mb-4">添加文档</h2>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium mb-1">标题 *</label>
                <input type="text" value={docTitle} onChange={e => setDocTitle(e.target.value)} className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">内容 *</label>
                <textarea value={docContent} onChange={e => setDocContent(e.target.value)} rows={10}
                  placeholder="输入文档内容，将自动按段落分块..."
                  className="w-full px-3 py-2 border rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
            </div>
            <div className="flex gap-3 justify-end mt-6">
              <button onClick={() => setAddDocOpen(false)} className="px-4 py-2 border rounded-lg text-sm">取消</button>
              <button onClick={handleAddDoc} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm">添加</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default KnowledgePage
