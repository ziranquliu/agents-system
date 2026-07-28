import { Link } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'

export default function Header() {
  const { user, logout } = useAuthStore()

  const handleLogout = async () => {
    await logout()
  }

  return (
    <header className="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-6">
      <div className="text-sm text-gray-500">
        {user ? (
          <span>欢迎回来，{user.display_name || user.username}</span>
        ) : (
          <span>开发环境</span>
        )}
      </div>
      <div className="flex items-center gap-4">
        <Link
          to="/dashboard"
          className="text-sm text-gray-500 hover:text-gray-700 transition-colors"
        >
          总览看板
        </Link>
        {user ? (
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-600">
              {user.display_name || user.username}
            </span>
            <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center text-white text-sm font-medium">
              {(user.display_name || user.username).charAt(0).toUpperCase()}
            </div>
            <button
              onClick={handleLogout}
              className="text-sm text-gray-400 hover:text-red-500 transition-colors"
            >
              退出
            </button>
          </div>
        ) : (
          <Link
            to="/login"
            className="text-sm text-blue-600 hover:text-blue-700 transition-colors"
          >
            登录
          </Link>
        )}
      </div>
    </header>
  )
}
