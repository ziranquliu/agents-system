import { NavLink } from 'react-router-dom'

const navItems = [
  { path: '/dashboard', label: '\u603B\u89C8\u770B\u677F', icon: '\uD83D\uDCCA' },
  { path: '/agents', label: 'Agent \u7BA1\u7406', icon: '\uD83E\uDD16' },
  { path: '/conversations', label: '\u5BF9\u8BDD\u7BA1\u7406', icon: '\uD83D\uDCAC' },
  { path: '/models', label: '\u6A21\u578B\u914D\u7F6E', icon: '\uD83E\uDDE0' },
  { path: '/skills', label: 'Skill \u7BA1\u7406', icon: '\uD83D\uDD27' },
  { path: '/skill-market', label: '  Skill \u5E02\u573A', icon: '\uD83D\uDED2' },
  { path: '/agent-market', label: '  Agent \u5E02\u573A', icon: '\uD83E\uDDE0' },
  { path: '/model-market', label: '  \u6A21\u578B\u5E02\u573A', icon: '\uD83E\uDDE0' },
  { path: '/mcp', label: 'MCP \u670D\u52A1', icon: '\uD83D\uDD0C' },
  { path: '/mcp-market', label: '  MCP \u5E02\u573A', icon: '\uD83D\uDED2' },
  { path: '/workspaces', label: '\u5DE5\u4F5C\u7A7A\u95F4', icon: '\uD83D\uDCC1' },
  { path: '/users', label: '\u7528\u6237\u7BA1\u7406', icon: '\uD83D\uDC64' },
  { path: '/operation-logs', label: '\u64CD\u4F5C\u65E5\u5FD7', icon: '\uD83D\uDCDD' },
  { path: '/scanner', label: '\u7EC4\u4EF6\u626B\u63CF', icon: '\uD83D\uDD0D' },
  { path: '/updates', label: '\u66F4\u65B0\u68C0\u6D4B', icon: '\uD83D\uDD04' },
  { path: '/collaborations', label: '\u534F\u4F5C\u7BA1\u7406', icon: '\uD83E\uDD1D' },
  { path: '/skill-optimization', label: 'Skill \u4F18\u5316', icon: '\u26A1' },
  { path: '/mcp-optimization', label: 'MCP \u4F18\u5316', icon: '\uD83D\uDD0C' },
  { path: '/conversation-enhancement', label: '\u4F1A\u8BDD\u589E\u5F3A', icon: '\uD83D\uDCDD' },
  { path: '/knowledge', label: '\u77E5\u8BC6\u5E93', icon: '\uD83D\uDCDA' },
]

export default function Sidebar() {
  return (
    <aside className="w-60 bg-sidebar-bg flex flex-col h-screen sticky top-0">
      <div className="p-4 border-b border-gray-700/50">
        <h1 className="text-lg font-bold text-sidebar-text-active">{'\u667A\u80FD\u4F53\u7BA1\u7406\u7CFB\u7EDF'}</h1>
      </div>
      <nav className="flex-1 p-2 space-y-1 overflow-y-auto">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all duration-150 ${
                isActive
                  ? 'bg-sidebar-active text-sidebar-text-active font-medium shadow-sm'
                  : 'text-sidebar-text hover:bg-sidebar-hover hover:text-white'
              }`
            }
          >
            <span className="text-lg">{item.icon}</span>
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
