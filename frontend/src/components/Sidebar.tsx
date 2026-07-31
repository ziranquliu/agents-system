import { NavLink } from 'react-router-dom'

const navItems = [
  { path: '/dashboard', label: '\u603B\u89C8\u770B\u677F', icon: '\uD83D\uDCCA' },
  { path: '/agents', label: 'Agent \u7BA1\u7406', icon: '\uD83E\uDD16' },
  { path: '/conversations', label: '\u5BF9\u8BDD\u7BA1\u7406', icon: '\uD83D\uDCAC' },
  { path: '/models', label: '\u6A21\u578B\u914D\u7F6E', icon: '\uD83E\uDDE0' },
  { path: '/skills', label: 'Skill \u7BA1\u7406', icon: '\uD83D\uDD27' },
  { path: '/batch-install', label: '\u6279\u91CF\u5B89\u88C5', icon: '\uD83D\uDCE6' },
  { path: '/skill-reuse', label: '\u590D\u7528', icon: '\uD83D\uDD04' },
  { path: '/skill-market', label: '  Skill \u5E02\u573A', icon: '\uD83D\uDED2' },
  { path: '/agent-market', label: '  Agent \u5E02\u573A', icon: '\uD83E\uDDE0' },
  { path: '/model-market', label: '  \u6A21\u578B\u5E02\u573A', icon: '\uD83E\uDDE0' },
  { path: '/model-templates', label: '\u6A21\u578B\u6A21\u677F', icon: '\u2699\uFE0F' },
  { path: '/mcp', label: 'MCP \u670D\u52A1', icon: '\uD83D\uDD0C' },
  { path: '/mcp-batch', label: 'MCP\u6279\u91CF\u5B89\u88C5', icon: '\u26A1' },
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
  { path: '/dialogue-enhancement', label: '\u5BF9\u8BDD\u589E\u5F3A', icon: '\uD83D\uDCAC' },
  { path: '/knowledge', label: '\u77E5\u8BC6\u5E93', icon: '\uD83D\uDCDA' },
  { path: '/tasks', label: '\u4EFB\u52A1\u7BA1\u7406', icon: '\u2705' },
  { path: '/agent-memory', label: '\u8BB0\u5FC6\u7BA1\u7406', icon: '\uD83E\uDDE0' },
  { path: '/system-monitor', label: '\u7CFB\u7EDF\u76D1\u63A7', icon: '\uD83D\uDCCA' },
  { path: '/monitoring', label: '\u76D1\u63A7\u770B\u677F', icon: '\uD83D\uDCCA' },
  { path: '/ops', label: '\u81EA\u52A8\u5316\u8FD0\u7EF4', icon: '\u2699\uFE0F' },
  { path: '/backup-enhanced', label: '\u5907\u4EFD\u4E0E\u6062\u590D\u589E\u5F3A', icon: '\uD83D\uDCDA' },
  { path: '/health', label: '\u5065\u5EB7\u76D1\u63A7', icon: '\uD83D\uDCAA' },
  { path: '/audit', label: '\u64CD\u4F5C\u5BA1\u8BA1', icon: '\uD83D\uDD12' },
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
