import { Link } from 'react-router-dom'
export default function NotFound() {
  return <div className="min-h-screen flex flex-col items-center justify-center gap-4"><h1 className="text-4xl font-bold">404</h1><p className="text-gray-500">页面不存在</p><Link to="/" className="text-blue-500 hover:underline">返回首页</Link></div>
}
