import { type ReactNode } from 'react'

interface LoadingProps {
  /** 加载提示文字 */
  text?: string
  /** 全屏/整块居中模式（默认 inline） */
  fullPage?: boolean
  /** 自定义尺寸 (px) */
  size?: number
  /** 额外类名 */
  className?: string
}

const Spinner = ({ size = 20 }: { size?: number }) => (
  <svg
    className="animate-spin text-blue-600"
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
  >
    <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" className="opacity-20" />
    <path
      d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
      fill="currentColor"
      className="opacity-80"
    />
  </svg>
)

/** 加载指示器 — inline（默认） / fullPage 两种模式 */
export default function Loading({
  text = '加载中...',
  fullPage = false,
  size,
  className = '',
}: LoadingProps) {
  if (fullPage) {
    return (
      <div className={`flex items-center justify-center min-h-[300px] ${className}`}>
        <div className="flex flex-col items-center gap-3 text-gray-400">
          <Spinner size={size ?? 36} />
          <span className="text-sm">{text}</span>
        </div>
      </div>
    )
  }

  return (
    <span className={`inline-flex items-center gap-2 text-gray-400 text-sm ${className}`}>
      <Spinner size={size} />
      {text && <span>{text}</span>}
    </span>
  )
}

interface LoadingOverlayProps {
  visible: boolean
  text?: string
  children?: ReactNode
}

/** 覆盖层加载（在父元素上绝对定位） */
export function LoadingOverlay({ visible, text = '加载中...', children }: LoadingOverlayProps) {
  if (!visible) return <>{children}</>
  return (
    <div className="relative">
      {children}
      <div className="absolute inset-0 bg-white/70 flex items-center justify-center z-10 rounded-xl">
        <div className="flex flex-col items-center gap-2">
          <Spinner size={28} />
          <span className="text-sm text-gray-500">{text}</span>
        </div>
      </div>
    </div>
  )
}
