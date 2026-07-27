import { NavLink } from 'react-router-dom'

const navItems = [
  { path: '/dashboard', label: '\u603B\u89C8\u770B\u677F', icon: '\uD83D\uDCCA' },
  { path: '/agents', label: 'Agent \u7BA1\u7406', icon: '\uD83E\uDD16' },
  { path: '/conversations', label: '\u5BF9\u8BDD\u7BA1\u7406', icon: '\uD83D\uDCAC' },
  { path: '/models', label: '\u6A21\u578B\u914D\u7F6E', icon: '\uD83E\uDDE0' },
  { path: '/skills', label: 'Skill \u7BA1\u7406', icon: '\uD83D\uDD27' },
  { path: '/mcp', label: 'MCP \u670D\u52A1', icon: '\uD83D\uDD0C' },
  { path: '/workspaces', label: '\u5DE5\u4F5C\u7A7A\u95F4', icon: '\uD83D\uDCC1' },
]

export default function Sidebar() {
  return (
    <aside className="w-60 bg-white border-r border-gray-200 flex flex-col">
      <div className="p-4 border-b border-gray-200">
        <h1 className="text-lg font-bold text-gray-800">{'\u667A\u80FD\u4F53\u7BA1\u7406\u7CFB\u7EDF'}</h1>
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
