import { NavLink } from 'react-router-dom'

const navItems = [
  { path: '/dashboard', label: '总览看板', icon: '📊' },
  { path: '/agents', label: 'Agent 管理', icon: '🤖' },
  { path: '/conversations', label: '对话管理', icon: '💬' },
  { path: '/models', label: '模型配置', icon: '🧠' },
  { path: '/skills', label: 'Skill 管理', icon: '🔧' },
  { path: '/mcp', label: 'MCP 服务', icon: '🔌' },
  { path: '/workspaces', label: '工作空间', icon: '📁' },
]

export default function Sidebar() {
  return (
    <aside className="w-60 bg-white border-r border-gray-200 flex flex-col">
      <div className="p-4 border-b border-gray-200">
        <h1 className="text-lg font-bold text-gray-800">智能体管理系统</h1>
      </div>
      <nav className="flex-1 p-2 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                isActive
                  ? 'bg-blue-50 text-blue-700 font-medium'
                  : 'text-gray-600 hover:bg-gray-50'
              }`
            }
          >
            <span>{item.icon}</span>
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
