export default function Header() {
  return (
    <header className="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-6">
      <div className="text-sm text-gray-500">本地开发环境</div>
      <div className="flex items-center gap-4">
        <span className="text-sm text-gray-600">管理员</span>
        <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center text-white text-sm font-medium">
          A
        </div>
      </div>
    </header>
  )
}
