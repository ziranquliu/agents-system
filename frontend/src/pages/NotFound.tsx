import { Link } from 'react-router-dom'
export default function NotFound() {
  return <div className="min-h-screen flex flex-col items-center justify-center gap-4"><h1 className="text-4xl font-bold">404</h1><p className="text-gray-500">{'\u9875\u9762\u4E0D\u5B58\u5728'}</p><Link to="/" className="text-blue-500 hover:underline">{'\u8FD4\u56DE\u9996\u9875'}</Link></div>
}
