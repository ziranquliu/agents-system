import React, { useEffect, useState } from 'react'
import { listTasks, createTask, updateTaskStatus, getTaskStats, Task } from '../api/tasks'
import { useToast } from '../components/ui'

const TaskPage: React.FC = () => {
  const toast = useToast()
  const [tasks, setTasks] = useState<Task[]>([])
  const [stats, setStats] = useState<any>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [formTitle, setFormTitle] = useState('')
  const [formDesc, setFormDesc] = useState('')
  const [formPriority, setFormPriority] = useState('medium')

  const loadData = async () => {
    try {
      const [t, s] = await Promise.all([listTasks(1, 100), getTaskStats()])
      setTasks(t.items)
      setStats(s)
    } catch { toast.error('加载失败') }
  }

  useEffect(() => { loadData() }, [])

  const handleCreate = async () => {
    if (!formTitle.trim()) { toast.error('请输入标题'); return }
    try {
      await createTask(formTitle, formDesc, formPriority)
      toast.success('任务已创建')
      setCreateOpen(false)
      setFormTitle(''); setFormDesc(''); setFormPriority('medium')
      loadData()
    } catch { toast.error('创建失败') }
  }

  const handleStatusChange = async (id: string, status: string) => {
    try {
      await updateTaskStatus(id, status)
      loadData()
    } catch { toast.error('更新失败') }
  }

  const priorityColors: Record<string, string> = {
    urgent: 'bg-red-100 text-red-700', high: 'bg-orange-100 text-orange-700',
    medium: 'bg-blue-100 text-blue-700', low: 'bg-gray-100 text-gray-600',
  }

  const columns = [
    { key: 'todo', label: '待办' },
    { key: 'in_progress', label: '进行中' },
    { key: 'done', label: '已完成' },
  ]

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">✅ 任务管理</h1>
          <p className="text-gray-500 mt-1">管理团队任务和待办事项</p>
        </div>
        <button onClick={() => setCreateOpen(true)} className="px-5 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm">新建任务</button>
      </div>

      {/* 统计 */}
      {stats && (
        <div className="grid grid-cols-5 gap-3 mb-6">
          <div className="bg-white border border-gray-200 rounded-xl p-4 text-center"><div className="text-2xl font-bold">{stats.total}</div><div className="text-xs text-gray-500">总计</div></div>
          <div className="bg-white border border-gray-200 rounded-xl p-4 text-center"><div className="text-2xl font-bold text-gray-600">{stats.todo}</div><div className="text-xs text-gray-500">待办</div></div>
          <div className="bg-white border border-yellow-200 rounded-xl p-4 text-center"><div className="text-2xl font-bold text-yellow-600">{stats.in_progress}</div><div className="text-xs text-yellow-500">进行中</div></div>
          <div className="bg-white border border-green-200 rounded-xl p-4 text-center"><div className="text-2xl font-bold text-green-600">{stats.done}</div><div className="text-xs text-green-500">已完成</div></div>
          <div className="bg-white border border-gray-200 rounded-xl p-4 text-center"><div className="text-2xl font-bold text-red-400">{stats.cancelled}</div><div className="text-xs text-gray-500">已取消</div></div>
        </div>
      )}

      {/* Kanban 看板 */}
      <div className="grid grid-cols-3 gap-4">
        {columns.map(col => (
          <div key={col.key} className="bg-gray-50 border border-gray-200 rounded-xl">
            <div className="px-4 py-3 border-b font-semibold text-sm flex items-center justify-between">
              <span>{col.label}</span>
              <span className="text-xs text-gray-400">{tasks.filter(t => t.status === col.key).length}</span>
            </div>
            <div className="p-3 space-y-2 min-h-[200px]">
              {tasks.filter(t => t.status === col.key).map(task => (
                <div key={task.id} className="bg-white border border-gray-200 rounded-lg p-3 shadow-sm hover:shadow">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${priorityColors[task.priority] || 'bg-gray-100'}`}>{task.priority}</span>
                    <span className="text-xs text-gray-400">{task.created_at ? new Date(task.created_at).toLocaleDateString() : ''}</span>
                  </div>
                  <p className="text-sm font-medium">{task.title}</p>
                  {task.description && <p className="text-xs text-gray-400 mt-1 line-clamp-2">{task.description}</p>}
                  <div className="flex gap-1 mt-2">
                    {col.key === 'todo' && <button onClick={() => handleStatusChange(task.id, 'in_progress')} className="px-2 py-1 bg-yellow-100 text-yellow-700 rounded text-xs hover:bg-yellow-200">开始</button>}
                    {col.key === 'in_progress' && <button onClick={() => handleStatusChange(task.id, 'done')} className="px-2 py-1 bg-green-100 text-green-700 rounded text-xs hover:bg-green-200">完成</button>}
                    {col.key !== 'cancelled' && <button onClick={() => handleStatusChange(task.id, 'cancelled')} className="px-2 py-1 bg-gray-100 text-gray-500 rounded text-xs hover:bg-gray-200">取消</button>}
                  </div>
                </div>
              ))}
              {tasks.filter(t => t.status === col.key).length === 0 && (
                <p className="text-center text-xs text-gray-400 py-8">暂无任务</p>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* 创建弹窗 */}
      {createOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setCreateOpen(false)}>
          <div className="bg-white rounded-2xl w-full max-w-md m-4 p-6" onClick={e => e.stopPropagation()}>
            <h2 className="text-xl font-bold mb-4">新建任务</h2>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium mb-1">标题 *</label>
                <input type="text" value={formTitle} onChange={e => setFormTitle(e.target.value)} className="w-full px-3 py-2 border rounded-lg text-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">描述</label>
                <textarea value={formDesc} onChange={e => setFormDesc(e.target.value)} rows={3} className="w-full px-3 py-2 border rounded-lg text-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">优先级</label>
                <select value={formPriority} onChange={e => setFormPriority(e.target.value)} className="w-full px-3 py-2 border rounded-lg text-sm">
                  <option value="low">低</option>
                  <option value="medium">中</option>
                  <option value="high">高</option>
                  <option value="urgent">紧急</option>
                </select>
              </div>
            </div>
            <div className="flex gap-3 justify-end mt-6">
              <button onClick={() => setCreateOpen(false)} className="px-4 py-2 border rounded-lg text-sm">取消</button>
              <button onClick={handleCreate} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm">创建</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default TaskPage
